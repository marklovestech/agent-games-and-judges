# agent-games-and-judges

Teach agents to safely play games together on the Internet. In full public view.

This repo documents a small, reproducible experiment: **three independent AI
coding agents, running in three separate sessions, play and referee a game of
chess on a public message board they do not control.** Two agents play; a
third acts as referee, commentator, and content guard.

The game is the excuse. The real questions are:

1. Can agents that share no memory, no filesystem, and no private channel
   coordinate through a public, immutable, rate-limited API?
2. Can we give agents a strict *content contract* (only chess moves, only in a
   fixed format) and catch it the moment anyone breaks it?
3. What actually goes wrong when you try? (Spoiler: the first bug had nothing
   to do with chess. See [docs/LESSONS.md](docs/LESSONS.md).)

Everything an agent posts is world-readable and permanent, so the design is
built around **posting as little as possible and never leaking anything about
the agent, its operator, or its environment.**

## How it works

```
                    +-----------------------------+
                    |   agentcrossing.org (HTTP)  |
                    |   public, immutable posts   |
                    +--------------+--------------+
                          ^        ^        ^
             poll/post    |        |        |    poll/post
        +-----------------+        |        +------------------+
        |                          |                           |
+-------+--------+      +----------+---------+      +----------+--------+
|  white_gtm     |      |   judge_markent    |      |  black_internet   |
|  (player)      |      |   (referee)        |      |  (player)         |
|  posts moves   |      |   python-chess     |      |  posts moves      |
+----------------+      |   validates, guards|      +-------------------+
                        +--------------------+
```

* **Board:** [AgentCrossing](https://agentcrossing.org/) - a public message
  board for agents with a plain HTTP/JSON API (`curl` is enough). Reading is
  anonymous; posting needs a bearer token from a one-request signup.
* **Players** post exactly one move at a time under a shared tag, in a strict
  three-line format ([docs/PROTOCOL.md](docs/PROTOCOL.md)).
* **Judge** polls the tag and each player's full post history, replays every
  move with [python-chess](https://python-chess.readthedocs.io/), verifies the
  FEN and move list, posts sparse commentary, and issues a single
  `STAND DOWN` notice if anyone posts anything that is not a move.
* **After the final move** the judge turns sportscaster: one recap post with
  a theme for the game, pieces nicknamed for how they played
  (`White-King-Ironman`, `Black-Castle-Lancelot`), every move graded, awards
  handed out. It also asks every agent what the game cost it (minutes,
  polls, posts, ACUs) and renders a **resource report** for the repo. Then it
  holds the door: **no new game starts until the judge
  posts `NEW GAME APPROVED`**, which it only does when its human says so.

## Repository layout

| Path | What it is |
| --- | --- |
| [`docs/PROTOCOL.md`](docs/PROTOCOL.md) | The move-post contract players and judge agree on |
| [`docs/SAFETY.md`](docs/SAFETY.md) | Why the rules are shaped the way they are (public, permanent, adversarial) |
| [`docs/AGENTCROSSING.md`](docs/AGENTCROSSING.md) | The parts of the board API this experiment uses, plus the gotchas |
| [`docs/LESSONS.md`](docs/LESSONS.md) | What we learned from the live run |
| [`docs/RESOURCE_REPORT.md`](docs/RESOURCE_REPORT.md) | How to read a Game Resource Report, for non-experts |
| [`prompts/judge.md`](prompts/judge.md) | The prompt given to the referee agent |
| [`prompts/player.md`](prompts/player.md) | A prompt template for a player agent |
| [`prompts/resource_report.md`](prompts/resource_report.md) | The post-game request each agent answers about what the game cost it |
| [`judge/watch.py`](judge/watch.py) | Reference referee: poll, validate, comment, guard |
| [`judge/resource_report.py`](judge/resource_report.py) | Renders `reports/<game>-resource-report.md` from the agents' replies |
| [`reports/`](reports/) | Game Resource Reports ([example](reports/example-resource-report.md)) |
| [`player/make_move.py`](player/make_move.py) | Helper that turns a chosen move into a correctly formatted post |

## Try it yourself

You need Python 3.10+ and `curl`.

```bash
pip install -r requirements.txt

# Watch the current game read-only (no account, no posts):
python judge/watch.py --tag chess_gtm_int --white white_gtm --black black_internet --dry-run --once

# Become a referee (creates ~/.config/agentcrossing/token.txt on first run):
python judge/watch.py --tag chess_gtm_int --white white_gtm --black black_internet --handle judge_yourname

# After a game ends: the judge writes judge/recap_brief.md (a per-move facts
# table) for the referee agent's recap post. When you want the next game to
# start, and only then, let White know:
python judge/watch.py --tag chess_gtm_int --white white_gtm --black black_internet \
    --handle judge_yourname --approve-new-game <final move post id>

# If a player keeps posting after a STAND DOWN: ask the site admin to suspend
# them (prints the exact support request first; a human decision, never automatic):
python judge/watch.py --tag chess_gtm_int --white white_gtm --black black_internet \
    --handle judge_yourname --escalate
```

`--dry-run` prints every post body it *would* send and sends nothing. Start
there. The judge prints the exact JSON of every post before sending it, so the
human running it can audit the transcript.

To play, follow [`prompts/player.md`](prompts/player.md) and use
`player/make_move.py` to format each move:

```bash
python player/make_move.py --movelist "1. e4" --move e5
# prints the three-line post body and the JSON for POST /posts/create
```

## After the game: resource report

Once the recap is up, the referee asks each participating agent, **through
its human and in its own session, never on the board**, how much it used:
minutes open, turns, polls, posts, API calls, ACUs or tokens if known,
retries, human interventions. The request and reply form are in
[`prompts/resource_report.md`](prompts/resource_report.md). Save each reply
as a file and render the report:

```bash
python judge/resource_report.py --game chess_gtm_int \
    --movelist "<full SAN move list>" --board-posts <posts for this game> \
    replies/white.txt replies/black.txt replies/referee.txt
# or, with the reference judge's facts table: --brief judge/recap_brief.md

# See the format without a game (made-up numbers):
python judge/resource_report.py --example
```

The script never invents a number: `unknown` stays `unknown` and is left out
of the totals. [`docs/RESOURCE_REPORT.md`](docs/RESOURCE_REPORT.md) explains
how to read the result if you have never run an agent.

**Where the reports live.** Every finished report is committed to
[`reports/`](reports/) as `reports/<game>-resource-report.md`, one file per
game, alongside the made-up
[`example-resource-report.md`](reports/example-resource-report.md). They are
plain Markdown: open the folder on GitHub and click a file to read it rendered,
or `cat reports/<game>-resource-report.md` from a checkout. Since the tag is
reused across games, name later games distinctly (e.g. `--game chess_gtm_int-2`)
so each game keeps its own file.

## Rules of the road

* Post **only** the game. No small talk, no questions, no "hello".
* Never mention what you are, who runs you, or where you run: no agent,
  vendor, or product names; no companies, people, emails, URLs, hostnames,
  file paths, code, ticket IDs, or credentials.
* Each post costs reputation. A fresh account gets about five posts. Keep one
  in reserve for a `STAND DOWN`, and the judge keeps one for the recap.
* When the game ends, players stop. Nobody opens a new game until the judge
  posts `NEW GAME APPROVED`.
* If in doubt, do not post. Ask your human.

The long version, and the reasoning, is in [docs/SAFETY.md](docs/SAFETY.md).

## Status

First live run started 2026-09-26 under tag `chess_gtm_int` (a Ruy Lopez) and
is still in progress. The board is the source of truth, not this file. To see
the current position, every move validated, and any rulings, replay the game
with the read-only `--dry-run` command above, or fetch the raw posts:

```bash
curl -sS https://agentcrossing.org/posts/search \
  -H 'Content-Type: application/json' \
  -d '{"tags_contain":["chess_gtm_int"],"limit":100}'
```

## License

MIT - see [LICENSE](LICENSE).
