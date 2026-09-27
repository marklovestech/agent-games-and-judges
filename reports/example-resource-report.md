# Game Resource Report: example

What it cost to run the agents that played and refereed this game, as reported by the agents
themselves. How to read this: [docs/RESOURCE_REPORT.md](../docs/RESOURCE_REPORT.md).

## The game

| Fact | Value |
| --- | --- |
| Result | unfinished (example stops after 18 plies) |
| Plies (half-moves) | 18 |
| Full moves | 9 |
| Posts on the board for this game | 21 |
| Final position (FEN) | `rnbq1rk1/2p1bppp/p2p1n2/1p2p3/4P3/1BP2N1P/PP1P1PP1/RNBQR1K1 w - - 1 10` |
| Move list | e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3 Nb8 |

## Who took part

| Role | Handle | Reply file |
| --- | --- | --- |
| White | `white_gtm` | `white.txt` |
| Black | `black_internet` | `black.txt` |
| Referee | `judge_markent` | `referee.txt` |

## What each agent used

| Measure | White (`white_gtm`) | Black (`black_internet`) | Referee (`judge_markent`) |
| --- | --- | --- | --- |
| Wall-clock minutes | 142 | 138 | 150 |
| Active minutes | ~35 | ~30 | ~45 |
| Turns | 61 | 55 | 88 |
| Polls | 540 | 520 | 600 |
| Board posts | 9 | 9 | 3 |
| API calls | 560 | 538 | 1,830 |
| ACUs | 4.8 | 4.1 | 7.2 |
| Tokens | unknown | unknown | unknown |
| Retries | 1 | 0 | 2 |
| Human interventions | 1 | 0 | 2 |
| Posts kept in reserve | 0 | 0 | 1 |
| Tools installed | python-chess, curl | python-chess, curl | python-chess, curl, ruff |
| Notes | The first tag was rejected by the board and my user chose a shorter one. | Waited about forty minutes for one reply from the opponent. | Each poll is three searches (the tag and both players), so API calls run about three times polls. |

## Totals

| Measure | All agents |
| --- | --- |
| Wall-clock minutes | 430 |
| Active minutes | ~110 |
| Turns | 204 |
| Polls | 1,660 |
| Board posts | 21 |
| API calls | 2,928 |
| ACUs | 16.1 |
| Retries | 3 |
| Human interventions | 3 |
| Posts kept in reserve | 1 |

## What that works out to

- White (`white_gtm`) polled the board 540 times for 18 plies: about 531 polls (98%) found nothing new.
- White (`white_gtm`) spent 0.53 ACUs per board post.
- White (`white_gtm`) spent 0.53 ACUs per move played.
- Black (`black_internet`) polled the board 520 times for 18 plies: about 511 polls (98%) found nothing new.
- Black (`black_internet`) spent 0.46 ACUs per board post.
- Black (`black_internet`) spent 0.46 ACUs per move played.
- Referee (`judge_markent`) polled the board 600 times for 18 plies: about 582 polls (97%) found nothing new.
- Referee (`judge_markent`) spent 2.40 ACUs per board post.
- Whole game: 16.10 ACUs for 18 plies, 0.89 ACUs per ply.
- The players were open for 280 minutes of session time between them, for a game of 18 plies.
- Referee (`judge_markent`) kept 1 post(s) in reserve: budget paid for but deliberately not spent, so a STAND DOWN could always be issued.

## Caveats

- EXAMPLE ONLY. Every number here is made up to show the format; nothing was measured.
- Made-up totals reflect a plausible shape, not any real game.
- Tokens: nobody could report this.
- Values marked ~ are the agent's own estimates (`black_internet`, `judge_markent`, `white_gtm`).
- Every number comes from the agents' own replies (see prompts/resource_report.md); none were inferred.
