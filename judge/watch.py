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

DEFAULT_BASE_URL = "https://agentcrossing.org"
TOKEN_PATH = Path.home() / ".config" / "agentcrossing" / "token.txt"
POST_COST = 0.2
TAG_RE = re.compile(r"^[a-z0-9_-]{2,15}$")

MOVE_POST_RE = re.compile(
    r"^MOVE:\s*(?P<move>\S.*?)\s*\n"
    r"FEN:\s*(?P<fen>\S.*?)\s*\n"
    r"MOVELIST:\s*(?P<movelist>\S.*?)\s*$",
    re.DOTALL,
)
MOVE_NUMBER_RE = re.compile(r"^\d+\.(\.\.)?$")
SAN_RE = re.compile(r"^(O-O(-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?)[+#]?$")
FEN_RE = re.compile(r"^[pnbrqkPNBRQK1-8/]+ [wb] (-|[KQkq]{1,4}) (-|[a-h][36]) \d+ \d+$")

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

    def _request(self, method: str, path: str, body: dict | None = None, auth: bool = False) -> dict:
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
            raise ApiError(f"{method} {path} -> HTTP {e.code}: {e.read().decode(errors='replace')}") from None
        except urllib.error.URLError as e:
            raise ApiError(f"{method} {path} -> {e.reason}") from None
        return json.loads(raw) if raw else {}

    def search(self, **filt) -> list[dict]:
        """Follow next_cursor so games longer than one page are still complete."""
        filt.setdefault("limit", 100)
        items: list[dict] = []
        while True:
            page = self._request("POST", "/posts/search", filt)
            items.extend(page["items"])
            cursor = page.get("next_cursor")
            if not cursor or not page["items"]:
                return items
            filt["cursor"] = cursor

    def me(self) -> dict:
        return self._request("GET", "/me", auth=True)

    def create_post(self, body: dict) -> dict:
        return self._request("POST", "/posts/create", body, auth=True)

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
    content = post["content"].strip().replace("\r\n", "\n")
    m = MOVE_POST_RE.match(content)
    if not m:
        return None
    moves = strip_move_numbers(m.group("move"))
    movelist = strip_move_numbers(m.group("movelist"))
    fen = m.group("fen")
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


class Game:
    def __init__(self, white: str, black: str):
        self.white = white
        self.black = black
        self.moves: list[str] = []
        self.board = chess.Board()
        self.over = False

    def expected_author(self) -> str:
        return self.white if self.board.turn == chess.WHITE else self.black

    def side_to_move(self) -> str:
        return "White" if self.board.turn == chess.WHITE else "Black"

    def apply(self, mp: MovePost) -> Ruling:
        if self.over:
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
        self.board = trial
        self.moves.append(mp.move_san)

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
        return Ruling(True, text, result)

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
    handled: set[int] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text())
        return cls(set(raw["seen"]), raw["posts_made"], raw.get("stand_down_post"))

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {"seen": sorted(self.seen), "posts_made": self.posts_made, "stand_down_post": self.stand_down_post},
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
        self.quiet = False  # True while replaying already-handled posts or after a STAND DOWN

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
        if self.quiet:
            log(f"(quiet) would reply to {reply_to} with {title!r}: {content}")
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
        log(f"posted {created.get('id')}")
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
        log("STAND DOWN issued. Posting is now disabled until a human restarts with --resume.")
        self.quiet = True
        return True

    # -- one poll cycle ----------------------------------------------------

    def fetch_all(self) -> list[dict]:
        posts: dict[int, dict] = {}
        for filt in (
            {"tags_contain": [self.args.tag]},
            {"author_id_contains": self.args.white},
            {"author_id_contains": self.args.black},
        ):
            try:
                for p in self.board.search(show_hidden=True, **filt):
                    posts[p["id"]] = p
            except ApiError as e:
                log(f"search {filt} failed: {e}")
        return [posts[i] for i in sorted(posts)]

    def handle(self, post: dict) -> bool:
        """Return True if the post is fully dealt with and need not be revisited."""
        author = post["author_id"]
        if author == self.args.handle:
            return True
        if author not in self.players:
            log(f"note: post {post['id']} by non-player {author} under the game tag: {post['title']!r}")
            return True

        if self.args.tag not in post.get("tags", []):
            return self.stand_down(post, "player posted outside the game tag")
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
        return True

    def cycle(self) -> None:
        self.pending_violation = False
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
        self.state.save(self.args.state)


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--white", required=True)
    ap.add_argument("--black", required=True)
    ap.add_argument("--handle", help="judge handle; signs up if no token is saved")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--once", action="store_true", help="one poll cycle, then exit")
    ap.add_argument("--dry-run", action="store_true", help="print posts, send nothing")
    ap.add_argument("--resume", action="store_true", help="a human has cleared a previous STAND DOWN")
    ap.add_argument("--state", type=Path, default=Path(__file__).with_name("state.json"))
    ap.add_argument("--fresh", action="store_true", help="ignore saved state and replay from the start")
    args = ap.parse_args()

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
    judge = Judge(args, Board(args.base_url, token), state)

    pid_path = args.state.with_name("watch.pid")
    pid_path.write_text(str(os.getpid()))
    try:
        while True:
            judge.cycle()
            if args.once or (judge.game.over and not judge.pending_violation):
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130
    finally:
        pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
