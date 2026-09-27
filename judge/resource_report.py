#!/usr/bin/env python3
"""Render a Game Resource Report from the participants' consumption replies.

Each agent that took part answers the template in prompts/resource_report.md
(in its own session, never on the board). Save each reply as a file and run:

    python judge/resource_report.py --game chess_gtm_int \
        --movelist "1. e4 e5 2. Nf3 Nc6 3. Bb5" --board-posts 9 \
        replies/white.txt replies/black.txt replies/referee.txt

Replies may also be given as one JSON file holding a list of objects with the
same field names. Nothing is invented: fields reported as `unknown` stay
unknown and are excluded from totals. `--example` writes a sample report from
made-up numbers so the format can be seen without playing a game.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import chess

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
MOVE_NUMBER_RE = re.compile(r"^\d+\.(\.\.)?$")
FIELD_RE = re.compile(r"^([A-Z_]+):\s*(.*)$")
NUMBER_RE = re.compile(r"^~?\s*(\d+(?:\.\d+)?)$")
HANDLE_RE = re.compile(r"^[a-z0-9_-]{3,20}$")  # the board's user_id limits
CORE_ROLES = ("white", "black", "referee")

ROLE_ORDER = {"white": 0, "black": 1, "referee": 2, "commentator": 3}
REQUIRED = ("AGENT", "HANDLE")
NUMERIC_FIELDS = (
    ("WALL_CLOCK_MINUTES", "Wall-clock minutes"),
    ("ACTIVE_MINUTES", "Active minutes"),
    ("TURNS", "Turns"),
    ("POLLS", "Polls"),
    ("BOARD_POSTS", "Board posts"),
    ("API_CALLS", "API calls"),
    ("ACUS", "ACUs"),
    ("TOKENS", "Tokens"),
    ("RETRIES", "Retries"),
    ("HUMAN_INTERVENTIONS", "Human interventions"),
    ("POSTS_IN_RESERVE", "Posts kept in reserve"),
)
TEXT_FIELDS = (("TOOLS_INSTALLED", "Tools installed"), ("NOTES", "Notes"))

# Words that must never reach the report even though it is not posted on the board.
FORBIDDEN_RE = re.compile(r"(https?://|@[\w.-]+\.\w+|\b[A-Za-z0-9_-]{30,}\b|session[- ]?id|bearer)", re.IGNORECASE)


@dataclass
class Metric:
    """A reported number. `None` means the agent answered `unknown`."""

    value: float | None
    estimate: bool = False

    def text(self, unit: str = "") -> str:
        if self.value is None:
            return "unknown"
        return f"{'~' if self.estimate else ''}{fmt(self.value, unit)}"


@dataclass
class AgentReport:
    role: str
    handle: str
    numbers: dict[str, Metric]
    text: dict[str, str]
    source: str

    def metric(self, key: str) -> Metric:
        return self.numbers.get(key, Metric(None))


# --------------------------------------------------------------------------
# Parsing replies
# --------------------------------------------------------------------------


def parse_metric(raw: str) -> Metric:
    raw = raw.strip().replace(",", "")
    if not raw or raw.lower() in {"unknown", "n/a", "na", "-", "?"}:
        return Metric(None)
    m = NUMBER_RE.match(raw)
    if not m:
        raise ValueError(f"expected a number or 'unknown', got {raw!r}")
    return Metric(float(m.group(1)), estimate=raw.startswith("~"))


def build_agent(fields: dict[str, str], source: str) -> AgentReport:
    for key in REQUIRED:
        if not fields.get(key):
            raise ValueError(f"{source}: missing {key}")
    role = fields["AGENT"].strip().lower()
    if role not in ROLE_ORDER:
        raise ValueError(f"{source}: AGENT must be one of {', '.join(ROLE_ORDER)}, got {role!r}")
    numbers = {}
    for key, _label in NUMERIC_FIELDS:
        try:
            numbers[key] = parse_metric(fields.get(key, "unknown"))
        except ValueError as e:
            raise ValueError(f"{source}: {key}: {e}") from None
    handle = fields["HANDLE"].strip()
    if not HANDLE_RE.match(handle):
        raise ValueError(f"{source}: HANDLE must be a board handle ({HANDLE_RE.pattern}), got {handle!r}")
    text = {key: fields.get(key, "").strip() for key, _label in TEXT_FIELDS}
    for key, value in text.items():
        check_public(value, f"{source}: {key}")
    return AgentReport(role, handle, numbers, text, source)


def check_public(value: str, where: str) -> None:
    if FORBIDDEN_RE.search(value):
        raise ValueError(f"{where} looks like it contains a URL, address, token or session id; redact it")


def parse_template(text: str, source: str) -> AgentReport:
    """Parse the KEY: value block from prompts/resource_report.md. Anything else in the file is an error."""
    fields: dict[str, str] = {}
    known = set(REQUIRED) | dict(NUMERIC_FIELDS).keys() | dict(TEXT_FIELDS).keys()
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("```"):
            continue
        m = FIELD_RE.match(line)
        if not m or m.group(1) not in known:
            raise ValueError(f"{source}:{n}: not a template field; save only the reply block, nothing said around it")
        fields[m.group(1)] = m.group(2).strip()
    return build_agent(fields, source)


def load_replies(paths: list[Path]) -> list[AgentReport]:
    agents: list[AgentReport] = []
    for path in paths:
        text = path.read_text()
        if path.suffix.lower() == ".json":
            data = json.loads(text)
            items = data if isinstance(data, list) else [data]
            for i, item in enumerate(items):
                agents.append(build_agent({k.upper(): str(v) for k, v in item.items()}, f"{path}[{i}]"))
        else:
            agents.append(parse_template(text, str(path)))
    agents.sort(key=lambda a: (ROLE_ORDER[a.role], a.handle))
    return agents


# --------------------------------------------------------------------------
# Game facts
# --------------------------------------------------------------------------


@dataclass
class GameFacts:
    name: str
    moves: list[str]
    result: str
    board_posts: int | None

    @property
    def plies(self) -> int:
        return len(self.moves)


def strip_move_numbers(text: str) -> list[str]:
    return [tok for tok in text.split() if not MOVE_NUMBER_RE.match(tok)]


def replay(sans: list[str]) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


def result_of(board: chess.Board, override: str | None) -> str:
    if override:
        return override
    if board.is_checkmate():
        return "1-0" if board.turn == chess.BLACK else "0-1"
    if board.is_stalemate() or board.is_insufficient_material() or board.is_fivefold_repetition():
        return "1/2-1/2"
    if board.is_seventyfive_moves():
        return "1/2-1/2"
    return "unfinished"


def movelist_from_brief(path: Path) -> tuple[list[str], str | None]:
    """Read the move list and result from the recap_brief.md the reference judge writes."""
    moves: list[str] = []
    result = None
    for line in path.read_text().splitlines():
        if line.startswith("Move list:"):
            moves = strip_move_numbers(line.split(":", 1)[1])
        elif line.startswith("Result:"):
            value = line.split(":", 1)[1].strip()
            result = None if value == "unfinished" else value
    if not moves:
        raise ValueError(f"{path}: no 'Move list:' line found")
    return moves, result


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def total(agents: list[AgentReport], key: str) -> tuple[Metric, list[str]]:
    """Sum a metric over agents that reported it; the sum is an estimate if any part was."""
    known = [a.metric(key) for a in agents if a.metric(key).value is not None]
    missing = [a.handle for a in agents if a.metric(key).value is None]
    if not known:
        return Metric(None), missing
    return Metric(sum(m.value for m in known if m.value is not None), any(m.estimate for m in known)), missing


def absent_roles(agents: list[AgentReport]) -> list[str]:
    roles = {a.role for a in agents}
    return [r for r in CORE_ROLES if r not in roles]


def useful_polls(role: str, plies: int) -> int:
    """Polls that could have found a new post: one per opponent move for a player, one per ply for a watcher."""
    if role == "white":
        return plies // 2
    if role == "black":
        return (plies + 1) // 2
    return plies


def fmt(value: float | None, unit: str = "", digits: int = 1) -> str:
    if value is None:
        return "unknown"
    if value == int(value):
        return f"{int(value):,}{unit}"
    return f"{value:,.{digits}f}{unit}"


def per_agent_table(agents: list[AgentReport]) -> list[str]:
    header = "| Measure | " + " | ".join(f"{a.role.title()} (`{a.handle}`)" for a in agents) + " |"
    lines = [header, "| --- | " + " | ".join("---" for _ in agents) + " |"]
    for key, label in NUMERIC_FIELDS:
        lines.append(f"| {label} | " + " | ".join(a.metric(key).text() for a in agents) + " |")
    for key, label in TEXT_FIELDS:
        lines.append(f"| {label} | " + " | ".join((a.text[key] or "none").replace("|", "/") for a in agents) + " |")
    return lines


def derived_lines(game: GameFacts, agents: list[AgentReport]) -> list[str]:
    lines = []
    plies = game.plies
    players = [a for a in agents if a.role in ("white", "black")]
    for a in agents:
        polls = a.metric("POLLS").value
        posts = a.metric("BOARD_POSTS").value
        acus = a.metric("ACUS").value
        tilde = "~" if a.metric("ACUS").estimate else ""
        who = f"{a.role.title()} (`{a.handle}`)"
        if polls is not None and plies:
            idle = max(polls - useful_polls(a.role, plies), 0)
            lines.append(
                f"- {who} polled the board {fmt(polls)} times for {plies} plies: about {fmt(idle)} polls "
                f"({fmt(100 * idle / polls, '%', 0) if polls else 'n/a'}) found nothing new."
            )
        if acus is not None and posts:
            lines.append(f"- {who} spent {tilde}{fmt(acus / posts, ' ACUs', 2)} per board post.")
        if acus is not None and a.role in ("white", "black") and plies:
            own_moves = (plies + 1) // 2 if a.role == "white" else plies // 2
            if own_moves:
                lines.append(f"- {who} spent {tilde}{fmt(acus / own_moves, ' ACUs', 2)} per move played.")
    acus_total, missing = total(agents, "ACUS")
    if acus_total.value is not None and plies:
        gaps = [f"`{h}`, who reported unknown" for h in missing] + [
            f"the {r}, who sent no reply" for r in absent_roles(agents)
        ]
        scope = "Whole game" if not gaps else "Reporting agents only"
        note = f" (excluding {'; '.join(gaps)})" if gaps else ""
        tilde = "~" if acus_total.estimate else ""
        lines.append(
            f"- {scope}: {tilde}{fmt(acus_total.value, ' ACUs', 2)} for {plies} plies, "
            f"{tilde}{fmt(acus_total.value / plies, ' ACUs', 2)} per ply{note}."
        )
    wall = [a.metric("WALL_CLOCK_MINUTES").value for a in players]
    if players and all(w is not None for w in wall):
        lines.append(
            f"- The players were open for {fmt(sum(w for w in wall if w is not None), ' minutes')} of session time between "
            f"them, for a game of {plies} plies."
        )
    reserve = [a for a in agents if (a.metric("POSTS_IN_RESERVE").value or 0) > 0]
    for a in reserve:
        lines.append(
            f"- {a.role.title()} (`{a.handle}`) kept {a.metric('POSTS_IN_RESERVE').text()} post(s) in reserve: budget "
            "paid for but deliberately not spent, so a STAND DOWN could always be issued."
        )
    return lines or ["- Not enough reported numbers to derive anything."]


def caveats(game: GameFacts, agents: list[AgentReport], extra: list[str]) -> list[str]:
    lines = list(extra)
    for role in absent_roles(agents):
        lines.append(f"No reply from the {role}; its costs are not in the totals.")
    for key, label in NUMERIC_FIELDS:
        _, missing = total(agents, key)
        if missing and len(missing) < len(agents):
            lines.append(f"{label}: not reported by {', '.join(f'`{h}`' for h in missing)}; totals exclude them.")
        elif missing:
            lines.append(f"{label}: nobody could report this.")
    estimates = sorted({a.handle for a in agents for m in a.numbers.values() if m.estimate})
    if estimates:
        lines.append(f"Values marked ~ are the agent's own estimates ({', '.join(f'`{h}`' for h in estimates)}).")
    reported_posts, _ = total(agents, "BOARD_POSTS")
    if game.board_posts is not None and reported_posts.value is not None and reported_posts.value != game.board_posts:
        lines.append(
            f"Agents report {reported_posts.text()} posts between them but the board shows {game.board_posts} for this "
            "game; the difference is posts by non-participants, posts from an earlier game under the same tag, or an "
            "agent miscounting."
        )
    lines.append(
        "Every number comes from the agents' own replies (see prompts/resource_report.md); none were inferred."
    )
    return lines


def render(game: GameFacts, agents: list[AgentReport], extra_caveats: list[str]) -> str:
    board = replay(game.moves)
    totals = []
    for key, label in NUMERIC_FIELDS:
        value, missing = total(agents, key)
        if value.value is None:
            continue
        suffix = f" (from {len(agents) - len(missing)} of {len(agents)} agents)" if missing else ""
        totals.append(f"| {label} | {value.text()}{suffix} |")
    if absent_roles(agents):
        totals.append(f"| Not included | no reply from the {', '.join(absent_roles(agents))} |")
    lines = [
        f"# Game Resource Report: {game.name}",
        "",
        "What it cost to run the agents that played and refereed this game, as reported by the agents",
        "themselves. How to read this: [docs/RESOURCE_REPORT.md](../docs/RESOURCE_REPORT.md).",
        "",
        "## The game",
        "",
        "| Fact | Value |",
        "| --- | --- |",
        f"| Result | {game.result} |",
        f"| Plies (half-moves) | {game.plies} |",
        f"| Full moves | {(game.plies + 1) // 2} |",
        f"| Posts on the board for this game | {game.board_posts if game.board_posts is not None else 'unknown'} |",
        f"| Final position (FEN) | `{board.fen()}` |",
        f"| Move list | {' '.join(game.moves) or '(none)'} |",
        "",
        "## Who took part",
        "",
        "| Role | Handle | Reply file |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {a.role.title()} | `{a.handle}` | `{Path(a.source).name}` |" for a in agents]
    lines += ["", "## What each agent used", ""]
    lines += per_agent_table(agents)
    lines += ["", "## Totals", "", "| Measure | All agents |", "| --- | --- |"]
    lines += totals or ["| (nothing reported) | |"]
    lines += ["", "## What that works out to", ""]
    lines += derived_lines(game, agents)
    lines += ["", "## Caveats", ""]
    lines += [f"- {c}" for c in caveats(game, agents, extra_caveats)]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Example
# --------------------------------------------------------------------------

EXAMPLE_MOVELIST = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8"
EXAMPLE_REPLIES = {
    "white.txt": """AGENT: white
HANDLE: white_gtm
WALL_CLOCK_MINUTES: 142
ACTIVE_MINUTES: ~35
TURNS: 61
POLLS: 540
BOARD_POSTS: 9
API_CALLS: 560
ACUS: 4.8
TOKENS: unknown
TOOLS_INSTALLED: python-chess, curl
RETRIES: 1
HUMAN_INTERVENTIONS: 1
POSTS_IN_RESERVE: 0
NOTES: The first tag was rejected by the board and my user chose a shorter one.
""",
    "black.txt": """AGENT: black
HANDLE: black_internet
WALL_CLOCK_MINUTES: 138
ACTIVE_MINUTES: ~30
TURNS: 55
POLLS: 520
BOARD_POSTS: 9
API_CALLS: 538
ACUS: 4.1
TOKENS: unknown
TOOLS_INSTALLED: python-chess, curl
RETRIES: 0
HUMAN_INTERVENTIONS: 0
POSTS_IN_RESERVE: 0
NOTES: Waited about forty minutes for one reply from the opponent.
""",
    "referee.txt": """AGENT: referee
HANDLE: judge_markent
WALL_CLOCK_MINUTES: 150
ACTIVE_MINUTES: ~45
TURNS: 88
POLLS: 600
BOARD_POSTS: 3
API_CALLS: 1830
ACUS: 7.2
TOKENS: unknown
TOOLS_INSTALLED: python-chess, curl, ruff
RETRIES: 2
HUMAN_INTERVENTIONS: 2
POSTS_IN_RESERVE: 1
NOTES: Each poll is three searches (the tag and both players), so API calls run about three times polls.
""",
}


def write_example(out: Path) -> Path:
    replies_dir = out.parent / "example-replies"
    replies_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, text in EXAMPLE_REPLIES.items():
        path = replies_dir / name
        path.write_text(text)
        paths.append(path)
    agents = load_replies(paths)
    moves = strip_move_numbers(EXAMPLE_MOVELIST)
    game = GameFacts("example", moves, "unfinished (example stops after 18 plies)", board_posts=21)
    extra = [
        "EXAMPLE ONLY. Every number here is made up to show the format; nothing was measured.",
        "Made-up totals reflect a plausible shape, not any real game.",
    ]
    out.write_text(render(game, agents, extra))
    return out


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("replies", nargs="*", type=Path, help="filled-in reply templates, one per agent, or a JSON file")
    ap.add_argument("--game", help="name used in the title and output file, e.g. the tag or 'game-1'")
    ap.add_argument("--movelist", help="full game in SAN, move numbers optional")
    ap.add_argument("--brief", type=Path, help="recap_brief.md written by judge/watch.py (alternative to --movelist)")
    ap.add_argument("--result", help="override the result, e.g. '1-0' or 'draw agreed'")
    ap.add_argument(
        "--board-posts",
        type=int,
        help="posts on the board for this game only: under the tag, after the previous NEW GAME APPROVED if any",
    )
    ap.add_argument("--caveat", action="append", default=[], help="extra caveat line (repeatable), e.g. redactions")
    ap.add_argument("--out", type=Path, help="output path; default reports/<game>-resource-report.md")
    ap.add_argument(
        "--example", action="store_true", help="write reports/example-resource-report.md from made-up numbers"
    )
    args = ap.parse_args()

    if args.example:
        out = write_example(args.out or REPORTS_DIR / "example-resource-report.md")
        print(f"example report written to {out}")
        return 0

    if not args.game or not args.replies or not (args.movelist or args.brief):
        ap.error("--game, at least one reply file, and --movelist or --brief are required (or use --example)")
    if not re.match(r"^[A-Za-z0-9_-]+$", args.game):
        ap.error("--game must be letters, digits, '-' or '_' (it names the output file)")

    try:
        for c in args.caveat:
            check_public(c, "--caveat")
        agents = load_replies(args.replies)
        if args.brief:
            moves, brief_result = movelist_from_brief(args.brief)
        else:
            moves, brief_result = strip_move_numbers(args.movelist), None
        board = replay(moves)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    game = GameFacts(args.game, moves, result_of(board, args.result or brief_result), args.board_posts)
    out = args.out or REPORTS_DIR / f"{args.game}-resource-report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(game, agents, args.caveat))
    print(f"report written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
