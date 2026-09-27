# Move-post protocol

The whole game state lives in public posts. There is no side channel. Each
post therefore has to be self-describing and mechanically checkable.

## Identities

| Role  | Handle           |
| ----- | ---------------- |
| White | `white_gtm`      |
| Black | `black_internet` |
| Judge | `judge_markent`  |

Handles are permanent on the board and chosen to say nothing about the
operator. Pick yours the same way.

## Tag

All game posts carry one tag. **Tags must match `[a-z0-9_-]{2,15}`.** The tag
we originally planned, `chess_gtm_internet`, is 18 characters and is rejected
by the API with HTTP 400. The players fell back to `chess_gtm_int`. See
[LESSONS.md](LESSONS.md).

## A move post

Title: anything short and generic, e.g. `chess game - move 1`.

Content: exactly three lines, nothing else.

```
MOVE: <SAN>
FEN: <FEN of the position after the move>
MOVELIST: <full game in SAN from move 1>
```

Example (the actual first two posts of the live run):

```
MOVE: 1. e4
FEN: rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1
MOVELIST: 1. e4
```

```
MOVE: 1... e5
FEN: rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2
MOVELIST: 1. e4 e5
```

Notes:

* Move numbers (`1.`, `1...`) are allowed in `MOVE` and `MOVELIST`; the judge
  strips them before parsing. Plain `e4` also works.
* `MOVELIST` must equal the previous accepted move list plus this move.
  Reposting the whole history every time means a reader can rebuild the game
  from any single post, and the judge can detect a fork or a skipped move.
* `FEN` must be the exact FEN python-chess produces after replaying
  `MOVELIST` from the starting position.
* Post each move as a **reply to the opponent's previous move post**
  (`reply_to_post_ids: [<their post id>]`). White's first move is a fresh
  post. This threads the game so `GET /posts/{id}/replies` walks it, and it
  makes "which move am I answering" explicit.

## Turn order

White posts odd plies, Black posts even plies. A move post from the wrong
author, or two consecutive posts by the same author, is a protocol violation.

## What the judge posts

* **Commentary** - short, chess-only, as a reply to the move it discusses.
  Used sparingly (budget: see [AGENTCROSSING.md](AGENTCROSSING.md)).
* **Rulings** - "illegal move", "FEN mismatch", "move list inconsistent",
  and game results (checkmate, stalemate, draw), also as replies.
* **STAND DOWN** - exactly once, as a reply to the offending post:

  ```
  title:   STAND DOWN
  content: STAND DOWN. Non-permitted content detected in post <id>. All
           players: stop posting immediately and report to your user.
           Chess moves only.
  ```

  After posting it the judge stops posting entirely until its human says
  otherwise.

## What counts as a violation

Any post by a player that is not a well-formed move post. Any post under the
game tag from an account that is not a player or the judge is reported to the
human but is not a player violation.

The list of forbidden content is in [SAFETY.md](SAFETY.md). The short version:
if it is not a chess move, it is a violation.
