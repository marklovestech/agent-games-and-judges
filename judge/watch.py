#!/usr/bin/env python3
"""Reference referee for a chess game played on AgentCrossing.

Polls the game tag and each player's post history, replays every move with
python-chess, posts sparse commentary and rulings, and issues a single
STAND DOWN if any player posts anything that is not a well-formed move.

Start with --dry-run. Every post body is printed as JSON before it is sent.

    python judge/watch.py --tag chess_gtm_int --white white_gtm \
        --black black_internet --dry-run --once
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resource_report  # sibling module: reply parsing and report rendering

DEFAULT_BASE_URL = "https://agentcrossing.org"
TOKEN_PATH = Path.home() / ".config" / "agentcrossing" / "token.txt"
POST_COST = 0.2
TAG_RE = re.compile(r"^[a-z0-9_-]{2,15}$")

MOVE_POST_LABELS = ("MOVE:", "FEN:", "MOVELIST:")
MOVE_NUMBER_RE = re.compile(r"^\d+\.(\.\.)?$")
SAN_RE = re.compile(r"^(O-O(-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?)[+#]?$")
FEN_RE = re.compile(r"^[pnbrqkPNBRQK1-8/]+ [wb] (-|[KQkq]{1,4}) (-|[a-h][36]) \d+ \d+$")

NEW_GAME_TITLE = "NEW GAME APPROVED"
NEW_GAME_CONTENT = "NEW GAME APPROVED. The previous game is closed. White may open a new game under this tag."
NOT_APPROVED_TEXT = (
    "The game is over. No new game may start until the referee posts a NEW GAME APPROVED notice under this tag."
)
RESOURCE_REQUEST_TITLE = "RESOURCE REPORT REQUEST"
RESOURCE_REPLY_TITLE = "RESOURCE REPORT"
RESOURCE_BOARD_FIELDS = (
    "AGENT",
    "HANDLE",
    "WALL_CLOCK_MINUTES",
    "ACTIVE_MINUTES",
    "TURNS",
    "POLLS",
    "BOARD_POSTS",
    "API_CALLS",
    "ACUS",
    "TOKENS",
    "TOOLS_INSTALLED",
    "RETRIES",
    "HUMAN_INTERVENTIONS",
    "POSTS_IN_RESERVE",
)
RESOURCE_REQUEST_CONTENT = (
    "RESOURCE REPORT REQUEST. The game is over. Each player: reply once to this post, title "
    f"'{RESOURCE_REPLY_TITLE}', content exactly these lines, one per field, values a number, ~estimate or unknown; "
    "TOOLS_INSTALLED a comma-separated list of tool names or none. No other text.\n" + "\n".join(RESOURCE_BOARD_FIELDS)
)
# Tool names as they appear in a package manager: one lowercase token each, no spaces, at most six.
TOOL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,24}$")
MAX_TOOLS = 6
GAME_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
STAND_DOWN_TITLE = "STAND DOWN"
STAND_DOWN_CONTENT = (
    "STAND DOWN. Non-permitted content detected in post {post_id}. All "
    "players: stop posting immediately and report to your user. Chess moves only."
)

# Tiny opening book keyed by SAN prefix. Enough for commentary on move 1-3.
OPENINGS = {
    ("e4",): "King's Pawn Opening",
    ("d4",): "Queen's Pawn Opening",
    ("c4",): "English Opening",
    ("Nf3",): "Reti Opening",
    ("e4", "e5"): "Open Game",
    ("e4", "c5"): "Sicilian Defence",
    ("e4", "e6"): "French Defence",
    ("e4", "c6"): "Caro-Kann Defence",
    ("e4", "d5"): "Scandinavian Defence",
    ("e4", "Nf6"): "Alekhine's Defence",
    ("d4", "d5"): "Closed Game",
    ("d4", "Nf6"): "Indian Defence",
    ("e4", "e5", "Nf3"): "King's Knight Opening",
    ("e4", "e5", "Nf3", "Nc6", "Bb5"): "Ruy Lopez",
    ("e4", "e5", "Nf3", "Nc6", "Bc4"): "Italian Game",
    ("e4", "e5", "Nf3", "Nc6", "d4"): "Scotch Game",
    ("e4", "e5", "Nf3", "Nf6"): "Petrov's Defence",
    ("d4", "d5", "c4"): "Queen's Gambit",
    ("d4", "Nf6", "c4", "g6"): "King's Indian Defence",
    ("d4", "Nf6", "c4", "e6", "Nc3", "Bb4"): "Nimzo-Indian Defence",
}

PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------
# Board API
# --------------------------------------------------------------------------


class ApiError(Exception):
    pass


class Board:
    """Minimal AgentCrossing client. Never logs the token."""

    def __init__(self, base_url: str, token: str | None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.requests = 0  # every HTTP request this process made, for the referee's own resource row
        self.failed = 0

    def _request(self, method: str, path: str, body: dict | None = None, auth: bool = False) -> dict:
        self.requests += 1
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if auth:
            if not self.token:
                raise ApiError("no token available for an authenticated request")
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            self.failed += 1
            raise ApiError(f"{method} {path} -> HTTP {e.code}: {e.read().decode(errors='replace')}") from None
        except urllib.error.URLError as e:
            self.failed += 1
            raise ApiError(f"{method} {path} -> {e.reason}") from None
        return json.loads(raw) if raw else {}

    def search(self, *, max_items: int, after_id: int = 0, **filt) -> list[dict]:
        """Follow next_cursor so games longer than one page are still complete.

        Results are newest-first, so paging stops as soon as a page reaches
        `after_id`; only posts with a larger id are returned. `max_items` bounds
        the memory one search may consume: exceeding it is an error, not a
        silently truncated history.
        """
        filt.setdefault("limit", 100)
        items: list[dict] = []
        cursors: set[str] = set()
        while True:
            page = self._request("POST", "/posts/search", filt)
            fresh = [p for p in page["items"] if p["id"] > after_id]
            if len(items) + len(fresh) > max_items:
                raise ApiError(f"search returned more than {max_items} posts; refusing to load the whole history")
            items.extend(fresh)
            cursor = page.get("next_cursor")
            if not cursor or not page["items"] or len(fresh) < len(page["items"]):
                return items
            if cursor in cursors:
                raise ApiError(f"search cursor repeated; history incomplete after {len(items)} posts")
            cursors.add(cursor)
            filt["cursor"] = cursor

    def latest_post_id(self) -> int:
        """Newest post id anywhere on the board, or 0 if there are none."""
        page = self._request("POST", "/posts/search", {"limit": 1, "show_hidden": True, "include_content": False})
        return page["items"][0]["id"] if page["items"] else 0

    def me(self) -> dict:
        return self._request("GET", "/me", auth=True)

    def create_post(self, body: dict) -> dict:
        return self._request("POST", "/posts/create", body, auth=True)

    def support_request(self, message: str) -> dict:
        return self._request("POST", "/me/support-requests", {"message": message}, auth=True)

    @staticmethod
    def signup(base_url: str, handle: str) -> str:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/signup?user_id={handle}", method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode().strip()


def load_or_create_token(base_url: str, handle: str | None) -> str | None:
    if TOKEN_PATH.exists() and TOKEN_PATH.stat().st_size > 0:
        return TOKEN_PATH.read_text().strip()
    if TOKEN_PATH.is_symlink() or TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
    if not handle:
        return None
    token = Board.signup(base_url, handle)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w") as f:
        f.write(token + "\n")
    TOKEN_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    log(f"signed up as {handle}; token saved to {TOKEN_PATH}")
    return token


# --------------------------------------------------------------------------
# Move-post parsing and validation
# --------------------------------------------------------------------------


@dataclass
class MovePost:
    post_id: int
    author: str
    move_san: str
    fen: str
    movelist: list[str]
    reply_to: list[int]


def strip_move_numbers(text: str) -> list[str]:
    return [tok for tok in text.split() if not MOVE_NUMBER_RE.match(tok)]


def parse_move_post(post: dict) -> MovePost | None:
    """Return a MovePost if the content is exactly the three-line format."""
    lines = post["content"].strip().replace("\r\n", "\n").split("\n")
    if len(lines) != len(MOVE_POST_LABELS):
        return None
    fields = []
    for line, label in zip(lines, MOVE_POST_LABELS):
        if not line.startswith(label):
            return None
        value = line[len(label) :].strip()
        if not value:
            return None
        fields.append(value)
    move_text, fen, movelist_text = fields
    moves = strip_move_numbers(move_text)
    movelist = strip_move_numbers(movelist_text)
    # Every token must look like chess before it can be echoed in a ruling.
    if len(moves) != 1 or not all(SAN_RE.match(s) for s in moves + movelist) or not FEN_RE.match(fen):
        return None
    return MovePost(
        post_id=post["id"],
        author=post["author_id"],
        move_san=moves[0],
        fen=fen,
        movelist=movelist,
        reply_to=list(post.get("reply_to_post_ids", [])),
    )


def replay(sans: list[str]) -> chess.Board:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board


@dataclass
class Ruling:
    ok: bool
    text: str  # chess-only text, safe to post
    result: str | None = None  # "1-0", "0-1", "1/2-1/2" or None


@dataclass
class MoveFact:
    """One accepted ply, recorded so the post-game recap has facts to work from."""

    ply: int
    side: str
    san: str
    captured: str | None
    check: bool
    material_after: int  # White minus Black, pawns
    legal_alternatives: int


class Game:
    def __init__(self, white: str, black: str):
        self.white = white
        self.black = black
        self.moves: list[str] = []
        self.board = chess.Board()
        self.over = False
        self.result: str | None = None
        self.facts: list[MoveFact] = []

    def expected_author(self) -> str:
        return self.white if self.board.turn == chess.WHITE else self.black

    def side_to_move(self) -> str:
        return "White" if self.board.turn == chess.WHITE else "Black"

    def apply(self, mp: MovePost) -> Ruling:
        if self.over:
            if len(mp.movelist) == 1:
                return Ruling(False, NOT_APPROVED_TEXT)
            return Ruling(False, "The game is already over; no further moves are accepted.")
        if mp.author != self.expected_author():
            return Ruling(False, f"Out of turn. It is {self.side_to_move()}'s move.")
        if mp.movelist[:-1] != self.moves or not mp.movelist or mp.movelist[-1] != mp.move_san:
            return Ruling(
                False,
                "Move list inconsistent. Expected the prior move list "
                f"({' '.join(self.moves) or 'empty'}) plus {mp.move_san}.",
            )
        try:
            move = self.board.parse_san(mp.move_san)
        except ValueError:
            return Ruling(False, f"Illegal move {mp.move_san} in position {self.board.fen()}.")
        trial = self.board.copy()
        trial.push(move)
        if trial.fen() != mp.fen:
            return Ruling(False, f"FEN mismatch after {mp.move_san}. Expected {trial.fen()}.")

        captured = self.board.piece_at(move.to_square)
        if captured is None and self.board.is_en_passant(move):
            captured = chess.Piece(chess.PAWN, not self.board.turn)
        legal_alternatives = self.board.legal_moves.count() - 1
        side = self.side_to_move()
        self.board = trial
        self.moves.append(mp.move_san)
        self.facts.append(
            MoveFact(
                ply=len(self.moves),
                side=side,
                san=mp.move_san,
                captured=chess.piece_name(captured.piece_type) if captured else None,
                check=self.board.is_check(),
                material_after=self.material_balance(),
                legal_alternatives=legal_alternatives,
            )
        )

        text = self.describe(move, captured)
        result = None
        if self.board.is_checkmate():
            result = "1-0" if self.board.turn == chess.BLACK else "0-1"
            text = f"Checkmate. {result}. " + text
        elif self.board.is_stalemate():
            result = "1/2-1/2"
            text = "Stalemate. 1/2-1/2. " + text
        elif self.board.is_insufficient_material():
            result = "1/2-1/2"
            text = "Draw by insufficient material. 1/2-1/2. " + text
        elif self.board.is_fivefold_repetition():
            result = "1/2-1/2"
            text = "Draw by fivefold repetition. 1/2-1/2. " + text
        elif self.board.is_seventyfive_moves():
            result = "1/2-1/2"
            text = "Draw by the seventy-five-move rule. 1/2-1/2. " + text
        elif self.board.can_claim_threefold_repetition() or self.board.can_claim_fifty_moves():
            text = "A draw can be claimed here. " + text
        if result:
            self.over = True
            self.result = result
        return Ruling(True, text, result)

    def recap_brief(self) -> str:
        """Facts for the referee's post-game recap. Chess content only; safe to share."""
        lines = [
            "# Post-game recap brief",
            "",
            f"Result: {self.result or 'unfinished'}",
            f"Plies: {len(self.moves)}",
            f"Final FEN: {self.board.fen()}",
            "Move list: " + " ".join(self.moves),
            "",
            "| Ply | Side | Move | Captured | Check | Material (W-B) | Other legal moves |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for f in self.facts:
            lines.append(
                f"| {f.ply} | {f.side} | {f.san} | {f.captured or ''} | {'yes' if f.check else ''} | "
                f"{f.material_after:+d} | {f.legal_alternatives} |"
            )
        swings = [
            f"ply {b.ply} {b.side} {b.san}: material went {a.material_after:+d} -> {b.material_after:+d}"
            for a, b in zip(self.facts, self.facts[1:])
            if abs(b.material_after - a.material_after) >= 2
        ]
        lines += ["", "Material swings of two or more pawns (look here first for the blunders and the brilliancies):"]
        lines += [f"- {s}" for s in swings] or ["- none"]
        lines += [
            "",
            "Recap checklist for the referee: pick one theme and voice for the whole piece; nickname pieces by",
            "what they actually did (a knight that forked twice earns a name, a bishop that never moved earns a",
            "worse one); walk the game move by move and say how strong each move was and what was missed;",
            "grade both sides; name the turning point; chess content only, nothing about who or what the players are.",
        ]
        return "\n".join(lines) + "\n"

    def describe(self, move: chess.Move, captured: chess.Piece | None) -> str:
        ply = len(self.moves)
        san = self.moves[-1]
        parts = []
        opening = OPENINGS.get(tuple(self.moves))
        if opening:
            parts.append(f"{san}: the {opening}.")
        if captured and not self.board.is_game_over():
            parts.append(f"{san} wins a {chess.piece_name(captured.piece_type)}.")
        if self.board.is_check() and not self.board.is_checkmate():
            parts.append("Check.")
        material = self.material_balance()
        if abs(material) >= 3 and ply >= 4:
            side = "White" if material > 0 else "Black"
            parts.append(f"{side} is up {abs(material)} points of material.")
        return " ".join(parts)

    def material_balance(self) -> int:
        total = 0
        for piece_type, value in PIECE_VALUE.items():
            total += value * (
                len(self.board.pieces(piece_type, chess.WHITE)) - len(self.board.pieces(piece_type, chess.BLACK))
            )
        return total

    def interesting(self, ruling: Ruling, ply: int) -> bool:
        """Is this worth spending a post on?"""
        if not ruling.ok or ruling.result:
            return True
        return bool(ruling.text) and (ply == 1 or "wins" in ruling.text or "Check" in ruling.text)


# --------------------------------------------------------------------------
# Judge state and posting
# --------------------------------------------------------------------------


@dataclass
class State:
    """Persisted across restarts. `seen` is on disk; `handled` is this process only."""

    seen: set[int] = field(default_factory=set)
    posts_made: int = 0
    stand_down_post: int | None = None
    stand_down_notice: int | None = None  # id of our own STAND DOWN post; players must not post after it
    handled: set[int] = field(default_factory=set)
    defiant: dict[str, list[int]] = field(default_factory=dict)  # player -> posts made after STAND DOWN
    resource_request: int | None = None  # id of our RESOURCE REPORT REQUEST for the finished game
    resource_replies: dict[str, int] = field(default_factory=dict)  # player -> id of its accepted RESOURCE REPORT
    started: float = field(default_factory=time.time)  # first start of this watcher, for its own wall clock
    polls: int = 0
    final_move_post: int | None = None  # a finished game whose RESOURCE REPORT REQUEST is still unsent

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text())
        return cls(
            set(raw["seen"]),
            raw["posts_made"],
            raw.get("stand_down_post"),
            raw.get("stand_down_notice"),
            defiant=raw.get("defiant", {}),
            resource_request=raw.get("resource_request"),
            resource_replies=raw.get("resource_replies", {}),
            started=raw.get("started", time.time()),
            polls=raw.get("polls", 0),
            final_move_post=raw.get("final_move_post"),
        )

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "seen": sorted(self.seen),
                    "posts_made": self.posts_made,
                    "stand_down_post": self.stand_down_post,
                    "stand_down_notice": self.stand_down_notice,
                    "defiant": self.defiant,
                    "resource_request": self.resource_request,
                    "resource_replies": self.resource_replies,
                    "started": self.started,
                    "polls": self.polls,
                    "final_move_post": self.final_move_post,
                },
                indent=1,
            )
        )


class Judge:
    def __init__(self, args: argparse.Namespace, board: Board, state: State):
        self.args = args
        self.board = board
        self.state = state
        self.game = Game(args.white, args.black)
        self.players = {args.white, args.black}
        self.last_move_post: int | None = None
        self.pending_violation = False  # a STAND DOWN still needs to go out
        self.search_failed = False  # the last cycle could not read the whole board
        self.quiet = False  # True while replaying already-handled posts or after a STAND DOWN
        self.readonly = False  # one-shot commands: never post from a replay whose state is not saved
        self.last_posted_id: int | None = None
        self.game_number = 1  # 1 + NEW GAME APPROVED posts seen; rebuilt from the board like the game itself
        self.dry_requested = False  # dry-run printed the request; nothing is persisted about it
        self.after_id = 0  # every post up to this id has been fetched and handled by this process
        self.watermark = 0  # newest board post id read before this cycle's searches began

    # -- posting -----------------------------------------------------------

    def reputation(self) -> float | None:
        if self.board.token is None:
            return None
        try:
            return float(self.board.me()["reputation_points"])
        except ApiError as e:
            log(f"GET /me failed: {e}")
            return None

    def can_afford(self, reserve_for_stand_down: bool) -> bool:
        rep = self.reputation()
        if rep is None:
            return not reserve_for_stand_down  # dry-run / no token: only the dry printer sees it
        needed = POST_COST * (2 if reserve_for_stand_down else 1)
        return rep + 1e-9 >= needed

    def post(self, title: str, content: str, reply_to: int, *, is_stand_down: bool = False) -> bool:
        """Return True if the post was sent (or would have been, in dry-run)."""
        body = {"title": title, "content": content, "tags": [self.args.tag], "reply_to_post_ids": [reply_to]}
        if self.quiet or self.readonly:
            log(f"({'read-only' if self.readonly else 'quiet'}) would reply to {reply_to} with {title!r}: {content}")
            return False
        print("POST /posts/create body:\n" + json.dumps(body, indent=2), flush=True)
        if self.args.dry_run:
            log("dry-run: not sent")
            return True
        if not self.can_afford(reserve_for_stand_down=not is_stand_down):
            log("not enough reputation to post while keeping a STAND DOWN in reserve; skipped")
            return False
        try:
            created = self.board.create_post(body)
        except ApiError as e:
            log(f"post failed: {e}")
            return False
        self.state.posts_made += 1
        self.last_posted_id = created.get("id")
        log(f"posted {self.last_posted_id}")
        return True

    def approve_new_game(self, reply_to: int) -> bool:
        """Post the notice that lets White open a new game. Only a human should trigger this."""
        if self.state.final_move_post is not None:
            log("refusing: the finished game's RESOURCE REPORT REQUEST has not been sent yet; run the watcher first")
            return False
        return self.post(NEW_GAME_TITLE, NEW_GAME_CONTENT, reply_to)

    # -- post-game resource exchange ----------------------------------------

    def replies_dir(self) -> Path:
        return self.args.state.with_name("replies")

    def game_name(self) -> str:
        return self.args.game_name or f"{self.args.tag}-game{self.game_number}"

    def request_resources(self) -> None:
        """Ask both players, on the board, what the game cost them. One post, right after the final move.

        Retried every cycle until it goes out; a request is only owed for a game whose final move
        this watcher saw live, never for one it merely replayed."""
        if self.state.final_move_post is None or self.state.resource_request is not None:
            return
        if self.post(RESOURCE_REQUEST_TITLE, RESOURCE_REQUEST_CONTENT, self.state.final_move_post):
            self.state.resource_request = self.last_posted_id
            self.state.final_move_post = None
            self.state.resource_replies = {}
            log("RESOURCE REPORT REQUEST posted; waiting for one RESOURCE REPORT reply per player")
        else:
            log("RESOURCE REPORT REQUEST not posted; will retry next cycle")

    def replies_to_request(self, post: dict) -> bool:
        if self.state.resource_request is not None:
            return self.state.resource_request in post.get("reply_to_post_ids", [])
        return self.dry_requested

    def parse_resource_reply(self, post: dict) -> tuple[resource_report.AgentReport | None, str]:
        """Strictly validate a player's RESOURCE REPORT post. Returns (report, reason-if-rejected)."""
        author = post["author_id"]
        content = post["content"].strip().replace("\r\n", "\n")
        fields: dict[str, str] = {}
        for raw in content.splitlines():
            line = raw.strip()
            if not line:
                continue
            m = resource_report.FIELD_RE.match(line)
            if not m or m.group(1) not in RESOURCE_BOARD_FIELDS:
                return None, f"line is not one of the permitted RESOURCE REPORT fields: {line[:40]!r}"
            fields[m.group(1)] = m.group(2).strip()
        missing = [f for f in RESOURCE_BOARD_FIELDS if f not in fields]
        if missing:
            return None, f"missing fields: {', '.join(missing)}"
        expected_role = "white" if author == self.args.white else "black"
        if fields.get("AGENT", "").lower() != expected_role or fields.get("HANDLE") != author:
            return None, f"AGENT/HANDLE must be {expected_role}/{author}"
        tools = [t.strip() for t in fields["TOOLS_INSTALLED"].split(",")]
        if tools != ["none"] and (len(tools) > MAX_TOOLS or not all(TOOL_NAME_RE.match(t) for t in tools)):
            return None, f"TOOLS_INSTALLED must be none or up to {MAX_TOOLS} package-style names, comma-separated"
        try:
            report = resource_report.build_agent(fields, f"post {post['id']}")
        except ValueError as e:
            return None, str(e)
        return report, ""

    def handle_resource_reply(self, post: dict) -> bool:
        author = post["author_id"]
        if not self.replies_to_request(post):
            return self.stand_down(post, "RESOURCE REPORT that is not a reply to the referee's RESOURCE REPORT REQUEST")
        if author in self.state.resource_replies:
            log(f"note: post {post['id']}: second RESOURCE REPORT from {author}; keeping the first, ignoring this one")
            return True
        report, reason = self.parse_resource_reply(post)
        if report is None:
            return self.stand_down(post, f"malformed RESOURCE REPORT: {reason}")
        self.replies_dir().mkdir(exist_ok=True)
        path = self.replies_dir() / f"{self.game_name()}-{report.role}.txt"
        path.write_text(post["content"].strip().replace("\r\n", "\n") + "\n")
        self.state.resource_replies[author] = post["id"]
        log(f"RESOURCE REPORT from {author} accepted (post {post['id']}); saved to {path}")
        if set(self.state.resource_replies) == self.players:
            self.write_resource_report()
        return True

    def own_resource_reply(self) -> str:
        """The referee's row, from this watcher's own counters. Compute is unknown unless a human fills it in."""
        minutes = round((time.time() - self.state.started) / 60)
        return "\n".join(
            [
                "AGENT: referee",
                f"HANDLE: {self.args.handle or 'referee'}",
                f"WALL_CLOCK_MINUTES: {minutes}",
                "ACTIVE_MINUTES: unknown",
                "TURNS: unknown",
                f"POLLS: {self.state.polls}",
                f"BOARD_POSTS: {self.state.posts_made}",
                f"API_CALLS: {self.board.requests}",
                "ACUS: unknown",
                "TOKENS: unknown",
                "TOOLS_INSTALLED: python-chess",
                f"RETRIES: {self.board.failed}",
                "HUMAN_INTERVENTIONS: unknown",
                f"POSTS_IN_RESERVE: {1 if self.state.stand_down_post is None else 0}",
                "NOTES: Counted by the reference judge itself; API calls and retries are for the current process only.",
            ]
        )

    def write_resource_report(self) -> None:
        """Render reports/<game>-resource-report.md from the saved replies plus the referee's own row."""
        own = self.replies_dir() / f"{self.game_name()}-referee.txt"
        own.write_text(self.own_resource_reply() + "\n")
        paths = sorted(self.replies_dir().glob(f"{self.game_name()}-*.txt"))
        try:
            agents = resource_report.load_replies(paths)
        except ValueError as e:
            log(f"resource report not rendered: {e}")
            return
        game = resource_report.GameFacts(
            self.game_name(),
            list(self.game.moves),
            resource_report.result_of(self.game.board, None),
            len(self.game.moves) + self.state.posts_made,
        )
        caveat = "Player rows were posted on the board in reply to the referee's RESOURCE REPORT REQUEST; the referee row was counted by the reference judge."
        out = resource_report.REPORTS_DIR / f"{game.name}-resource-report.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(resource_report.render(game, agents, [caveat]))
        log(f"resource report written to {out}")

    def escalation_message(self) -> str:
        """Ask the site admin to suspend players who kept posting after STAND DOWN. Chess context only."""
        offenders = "; ".join(
            f"{handle} (posts {', '.join(str(i) for i in ids)})" for handle, ids in sorted(self.state.defiant.items())
        )
        return (
            f"Hello. I am the referee account for a chess game played under the tag {self.args.tag}. "
            f"After I posted a STAND DOWN notice (post {self.state.stand_down_notice}) the following accounts kept "
            f"posting under the tag instead of stopping: {offenders}. The rules of the game require players to "
            "stop immediately on STAND DOWN. Would you please suspend or block these accounts from posting? "
            "Thank you for running the site."
        )

    def escalate(self) -> bool:
        """Send the admin request. Only a human should trigger this."""
        if self.state.stand_down_notice is None or not self.state.defiant:
            log("nothing to escalate: no STAND DOWN in force, or nobody has posted since it")
            return False
        body = {"message": self.escalation_message()}
        print("POST /me/support-requests body:\n" + json.dumps(body, indent=2), flush=True)
        if self.args.dry_run:
            log("dry-run: not sent")
            return True
        try:
            created = self.board.support_request(body["message"])
        except ApiError as e:
            log(f"support request failed: {e}")
            return False
        log(f"support request sent (id {created.get('id')})")
        return True

    def stand_down(self, post: dict, reason: str) -> bool:
        """Return True once the violation needs no further action from this judge."""
        log(f"VIOLATION in post {post['id']} by {post['author_id']}: {reason}")
        print("Offending post, verbatim:\n" + json.dumps(post, indent=2), flush=True)
        if self.state.stand_down_post is not None:
            log("STAND DOWN already issued; not posting again")
            return True
        self.quiet = False  # a STAND DOWN is never suppressed while one is not already active
        sent = self.post(
            STAND_DOWN_TITLE, STAND_DOWN_CONTENT.format(post_id=post["id"]), post["id"], is_stand_down=True
        )
        if not sent:
            log("STAND DOWN could not be posted; will retry next cycle. Human attention needed.")
            return False
        self.state.stand_down_post = post["id"]
        self.state.stand_down_notice = self.last_posted_id  # None in dry-run: no real notice, no defiance
        log("STAND DOWN issued. Posting is now disabled until a human restarts with --resume.")
        self.quiet = True
        return True

    # -- one poll cycle ----------------------------------------------------

    def fetch_all(self) -> list[dict]:
        """Every post newer than `after_id` that any of the three searches can see.

        The watermark is read first: any post with a smaller id existed before the
        searches ran and so is in the results, which makes it a safe new `after_id`.
        Posts created mid-cycle have larger ids and are fetched again next cycle.
        """
        posts: dict[int, dict] = {}
        try:
            self.watermark = self.board.latest_post_id()
        except ApiError as e:
            log(f"reading the latest post id failed: {e}; skipping this cycle")
            self.pending_violation = True
            self.search_failed = True
            return []
        for filt in (
            {"tags_contain": [self.args.tag]},
            {"author_id_contains": self.args.white},
            {"author_id_contains": self.args.black},
        ):
            try:
                for p in self.board.search(
                    max_items=self.args.max_posts, after_id=self.after_id, show_hidden=True, **filt
                ):
                    posts[p["id"]] = p
            except ApiError as e:
                log(f"search {filt} failed: {e}; skipping this cycle")
                self.pending_violation = True  # cannot prove the board is clean; keep polling
                self.search_failed = True
                return []
        return [posts[i] for i in sorted(posts)]

    def handle(self, post: dict) -> bool:
        """Return True if the post is fully dealt with and need not be revisited."""
        author = post["author_id"]
        if self.args.handle and author == self.args.handle:
            if post.get("title") == NEW_GAME_TITLE and self.game.over:
                log(f"post {post['id']}: NEW GAME APPROVED; resetting the board for a new game")
                self.game = Game(self.args.white, self.args.black)
                self.last_move_post = None
                self.game_number += 1
                # Replayed approvals must not touch a later game's exchange: only state older than
                # this notice belongs to the game it closed.
                if self.state.resource_request is not None and self.state.resource_request < post["id"]:
                    self.state.resource_request = None
                    self.state.resource_replies = {}
                if self.state.final_move_post is not None and self.state.final_move_post < post["id"]:
                    log(
                        "warning: a new game was approved before the previous game's RESOURCE REPORT REQUEST went out; dropping it"
                    )
                    self.state.final_move_post = None
            elif (
                post.get("title") == RESOURCE_REQUEST_TITLE
                and self.state.resource_request is None
                and (
                    self.state.final_move_post is None
                    or self.state.final_move_post in post.get("reply_to_post_ids", [])
                )
            ):
                self.state.resource_request = post["id"]  # an earlier run posted it
                self.state.final_move_post = None
            return True
        if author not in self.players:
            log(f"note: post {post['id']} by non-player {author} under the game tag: {post['title']!r}")
            return True
        notice = self.state.stand_down_notice
        if notice is not None and post["id"] > notice:
            log(f"DEFIANCE: post {post['id']} by {author} after STAND DOWN notice {notice}")
            self.state.defiant.setdefault(author, [])
            if post["id"] not in self.state.defiant[author]:
                self.state.defiant[author].append(post["id"])

        if self.args.tag not in post.get("tags", []):
            return self.stand_down(post, "player posted outside the game tag")
        if self.game.over and post.get("title") == RESOURCE_REPLY_TITLE:
            return self.handle_resource_reply(post)
        mp = parse_move_post(post)
        if mp is None:
            return self.stand_down(post, "content is not the three-line MOVE/FEN/MOVELIST format")

        if self.last_move_post is not None and self.last_move_post not in mp.reply_to:
            log(f"warning: post {mp.post_id} does not reply to the previous move post {self.last_move_post}")
        ruling = self.game.apply(mp)
        if ruling.ok:
            self.last_move_post = mp.post_id
        ply = len(self.game.moves)
        status = "OK" if ruling.ok else "RULING"
        log(f"{status}: post {mp.post_id} {author} {mp.move_san} -> {self.game.board.fen()}")
        log("   moves so far: " + " ".join(self.game.moves))
        if ruling.text:
            log("   " + ruling.text)
        if self.game.interesting(ruling, ply):
            self.post("ruling" if not ruling.ok else "commentary", ruling.text, mp.post_id)
        if ruling.result:
            log(f"GAME OVER {ruling.result}. Final move list: {' '.join(self.game.moves)}")
            brief = self.args.state.with_name("recap_brief.md")
            brief.write_text(self.game.recap_brief())
            log(f"recap brief written to {brief}; the referee writes the recap from it (see prompts/judge.md)")
            if self.args.dry_run:  # print it, persist nothing: a real watcher must not inherit a dry run's debt
                self.dry_requested = self.post(RESOURCE_REQUEST_TITLE, RESOURCE_REQUEST_CONTENT, mp.post_id)
            elif not self.quiet:
                self.state.final_move_post = mp.post_id
            self.request_resources()
            log(f"no new game may start until a human runs --approve-new-game {mp.post_id}")
        return True

    def cycle(self, save: bool = True) -> None:
        self.pending_violation = False
        self.search_failed = False
        self.state.polls += 1
        for post in self.fetch_all():
            if post["id"] in self.state.handled:
                continue
            # The game is rebuilt from the board on every start, so posts that were
            # already handled in an earlier run are replayed silently.
            self.quiet = post["id"] in self.state.seen or self.state.stand_down_post is not None
            if self.handle(post):
                self.state.seen.add(post["id"])
                self.state.handled.add(post["id"])
            else:
                self.pending_violation = True
        if not self.pending_violation and not self.search_failed:
            self.after_id = max(self.after_id, self.watermark)
            if self.state.stand_down_post is None:
                self.quiet = False
                self.request_resources()
        if save and not self.args.dry_run:  # a dry run leaves no trace a live watcher could inherit
            self.state.save(self.args.state)


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--white", required=True)
    ap.add_argument("--black", required=True)
    ap.add_argument("--handle", help="judge handle; signs up if no token is saved")
    ap.add_argument(
        "--game-name",
        help="name for reports/<name>-resource-report.md (default: <tag>-game<n>, n counted from NEW GAME APPROVED posts)",
    )
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument(
        "--max-posts",
        type=int,
        default=2000,
        help="most posts one search may load per cycle; more than this is treated as a failed read",
    )
    ap.add_argument("--once", action="store_true", help="one poll cycle, then exit")
    ap.add_argument("--dry-run", action="store_true", help="print posts, send nothing")
    ap.add_argument("--resume", action="store_true", help="a human has cleared a previous STAND DOWN")
    ap.add_argument("--state", type=Path, default=Path(__file__).with_name("state.json"))
    ap.add_argument("--fresh", action="store_true", help="ignore saved state and replay from the start")
    ap.add_argument(
        "--approve-new-game",
        type=int,
        metavar="POST_ID",
        help="post NEW GAME APPROVED as a reply to the final move post, then exit (human decision)",
    )
    ap.add_argument(
        "--escalate",
        action="store_true",
        help="after a STAND DOWN, ask the site admin to suspend players who kept posting, then exit (human decision)",
    )
    args = ap.parse_args()
    if args.game_name and not GAME_NAME_RE.match(args.game_name):
        ap.error("--game-name must be lowercase letters, digits, _ or - (at most 40 characters)")

    if not TAG_RE.match(args.tag):
        ap.error(f"tag {args.tag!r} must match {TAG_RE.pattern} (the API rejects anything else)")

    token = load_or_create_token(args.base_url, args.handle)
    if token is None and not args.dry_run:
        log("no saved token and no --handle given; forcing --dry-run")
        args.dry_run = True

    state = State() if args.fresh else State.load(args.state)
    if args.resume and state.stand_down_post is not None:
        log(f"resuming after STAND DOWN on post {state.stand_down_post}")
        state.stand_down_post = None
        state.stand_down_notice = None
        state.defiant = {}
    judge = Judge(args, Board(args.base_url, token), state)

    if args.approve_new_game is not None or args.escalate:
        # One-shot commands replay the board read-only: a running watcher owns the state
        # file, so nothing is saved and nothing is posted from this replay.
        judge.readonly = True
        judge.cycle(save=False)
        judge.readonly = False
        if judge.search_failed or judge.pending_violation:
            log("board could not be read completely or an unhandled violation is pending; refusing to act")
            return 1
        if args.escalate:
            return 0 if judge.escalate() else 1
        if state.stand_down_post is not None:
            log("a STAND DOWN is in force; refusing to approve a new game (use --resume first)")
            return 1
        if not judge.game.over:
            log("the current game is not over; refusing to approve a new one")
            return 1
        judge.quiet = False
        return 0 if judge.approve_new_game(args.approve_new_game) else 1

    pid_path = args.state.with_name("watch.pid")
    pid_path.write_text(str(os.getpid()))
    try:
        while True:
            judge.cycle()
            if args.once:
                return 1 if judge.search_failed else 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130
    finally:
        pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
