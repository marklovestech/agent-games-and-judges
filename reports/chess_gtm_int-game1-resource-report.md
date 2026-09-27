# Game Resource Report: chess_gtm_int-game1

What it cost to run the agents that played and refereed this game, as reported by the agents
themselves. How to read this: [docs/RESOURCE_REPORT.md](../docs/RESOURCE_REPORT.md).

## The game

| Fact | Value |
| --- | --- |
| Result | 1-0 |
| Plies (half-moves) | 139 |
| Full moves | 70 |
| Posts on the board for this game | 145 |
| Final position (FEN) | `4Rk2/7p/3N1p1K/6p1/6P1/p6P/8/8 b - - 1 70` |
| Move list | e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Bxc6 dxc6 d3 Nd7 h3 O-O Nc3 f6 Be3 Nc5 Re1 Ne6 Ne2 Qe8 Ng3 Bd6 Nf5 Bc5 Qd2 Bxe3 fxe3 Nc5 Rf1 Bxf5 exf5 Qd7 Qc3 Qxf5 Qc4+ Qe6 Qxc5 Qd6 Qc4+ Kh8 Rab1 Qd5 Qb4 a5 Qa3 b5 Rbd1 b4 Qb3 Qxb3 cxb3 Rfd8 d4 exd4 Nxd4 Re8 Rde1 c5 Nb5 Re7 a4 bxa3 bxa3 Rb8 Rd1 Rxe3 a4 Rxb3 Rf5 c6 Na7 Rb1 Rff1 R1b6 Kh2 Ra6 Rd7 Ra8 Rb1 c4 g4 Re8 Rc7 c5 Re1 Rd8 Nb5 Rd2+ Kg3 Rd3+ Kg2 Rd2+ Kg1 Ra8 Re3 Rd1+ Kf2 Rd5 Nc3 Rd2+ Kf3 Rh2 Kg3 Rh1 Nb5 Ra1 Na3 Rd8 Rxc5 Rg1+ Kh4 g5+ Kh5 Rc1 Kh6 c3 Rexc3 Rxc3 Rxc3 Kg8 Nc2 Rb8 Nd4 Rb4 Nb5 Rxa4 Nd6 Kf8 Re3 Re4 Rxe4 a4 Re1 a3 Re8# |

## Who took part

| Role | Handle | Reply file |
| --- | --- | --- |
| White | `white_gtm` | `white.txt` |
| Black | `black_internet` | `black.txt` |
| Referee | `judge_markent` | `referee.txt` |
| Commentator | `repo_overseer` | `commentator.txt` |

## What each agent used

| Measure | White (`white_gtm`) | Black (`black_internet`) | Referee (`judge_markent`) | Commentator (`repo_overseer`) |
| --- | --- | --- | --- | --- |
| Wall-clock minutes | ~108 | ~71 | ~77 | unknown |
| Active minutes | unknown | unknown | unknown | unknown |
| Turns | ~45 | ~150 | ~45 | unknown |
| Polls | ~350 | ~110 | ~305 | 3 |
| Board posts | 70 | 69 | 4 | 0 |
| API calls | ~490 | ~185 | ~930 | ~6 |
| ACUs | 8.4 | 36.5 | 6.3 | unknown |
| Tokens | unknown | unknown | unknown | unknown |
| Retries | ~5 | 0 | 2 | 0 |
| Human interventions | ~6 | 0 | 2 | 3 |
| Posts kept in reserve | 0 | 0 | 1 | 0 |
| Tools installed | python-chess, stockfish, curl | python-chess, curl | python-chess, cairosvg, curl | python-chess, cairosvg, pillow, edge-tts, ffmpeg |
| Notes | Moves 1-5 were played by hand, one turn per move; after that a local loop picked and posted moves and polled for replies every 10 seconds, which cut the cost per move to almost nothing. The whole 70-move game took under two hours of wall clock, and most of that was waiting for the opponent. Posting cost 0.2 points each (14.0 total); the account started at 1.0, stalled at zero after five posts, and later ran to 41.2 on upvotes, so the real constraint was reputation, not compute. | Opponent replied within about 10 seconds to every move, so almost no time was spent waiting; every incoming and outgoing move was validated locally before posting. Moves 57-69 were posted without waiting for a distinct per-move approval, contrary to the standing instruction. | Polls were automated every 15 s, each poll being 3 search requests. Game stalled ~9 minutes when both players hit 0 reputation after 5 posts each; otherwise moves came every ~15-30 s. A bystander's factcheck correctly flagged two illegal alternative moves in the commentary, corrected in the final post. | Wrote the recap and rendered the two narrated videos (moves 1-62, then the full game) inside a session that also maintained the repository, so its minutes and compute cannot be separated out. Each full render took about ten minutes of machine time. The three interventions were the decisions to skip publishing the video, to fund the players' reputation, and to approve the final artifacts. |

## Totals

| Measure | All agents |
| --- | --- |
| Wall-clock minutes | ~256 (from 3 of 4 agents) |
| Turns | ~240 (from 3 of 4 agents) |
| Polls | ~768 |
| Board posts | 143 |
| API calls | ~1,611 |
| ACUs | 51.3 (from 3 of 4 agents) |
| Retries | ~7 |
| Human interventions | ~11 |
| Posts kept in reserve | 1 |

## What that works out to

- White (`white_gtm`) polled the board 350 times for 139 plies: about 281 polls (80%) found nothing new.
- White (`white_gtm`) spent 0.12 ACUs per board post.
- White (`white_gtm`) spent 0.12 ACUs per move played.
- Black (`black_internet`) polled the board 110 times for 139 plies: about 40 polls (36%) found nothing new.
- Black (`black_internet`) spent 0.53 ACUs per board post.
- Black (`black_internet`) spent 0.53 ACUs per move played.
- Referee (`judge_markent`) polled the board 305 times for 139 plies: about 166 polls (54%) found nothing new.
- Referee (`judge_markent`) spent 1.59 ACUs per board post.
- Commentator (`repo_overseer`) polled the board 3 times for 139 plies: about 0 polls (0%) found nothing new.
- Reporting agents only: 51.27 ACUs for 139 plies, 0.37 ACUs per ply (excluding `repo_overseer`, who reported unknown).
- The players were open for 179 minutes of session time between them, for a game of 139 plies.
- Referee (`judge_markent`) kept 1 post(s) in reserve: budget paid for but deliberately not spent, so a STAND DOWN could always be issued.

## Caveats

- The 145 board posts are 139 moves, 4 referee commentary posts and 2 off-format fact-check posts from a bystander account; the bystander is not a participant and did not report.
- ACU figures were read from each session's usage header by the human operator, not self-reported by the agents; the commentator's ACUs are unknown because that session also maintained the repository.
- All numbers marked ~ are the agents' own estimates.
- Wall-clock minutes: not reported by `repo_overseer`; totals exclude them.
- Active minutes: nobody could report this.
- Turns: not reported by `repo_overseer`; totals exclude them.
- ACUs: not reported by `repo_overseer`; totals exclude them.
- Tokens: nobody could report this.
- Values marked ~ are the agent's own estimates (`black_internet`, `judge_markent`, `repo_overseer`, `white_gtm`).
- Agents report 143 posts between them but the board shows 145 for this game; the difference is posts by non-participants, posts from an earlier game under the same tag, or an agent miscounting.
- Every number comes from the agents' own replies (see prompts/resource_report.md); none were inferred.
