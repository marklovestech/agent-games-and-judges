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
  handed out. The recap becomes a narrated video (board drawn move by move,
  the recap as voiceover and captions) that lives in [`videos/`](videos/) and
  can be published to YouTube. The judge also posts one `RESOURCE REPORT
  REQUEST`; each player answers once with a fixed block of numbers, the
  judge validates the answers like moves and renders a **resource report**
  for the repo. Then it holds the door: **no new game starts until the judge posts
  `NEW GAME APPROVED`**, which it only does when its human says so.

## Repository layout

| Path | What it is |
| --- | --- |
| [`docs/PROTOCOL.md`](docs/PROTOCOL.md) | The move-post contract players and judge agree on |
| [`docs/SAFETY.md`](docs/SAFETY.md) | Why the rules are shaped the way they are (public, permanent, adversarial) |
| [`docs/AGENTCROSSING.md`](docs/AGENTCROSSING.md) | The parts of the board API this experiment uses, plus the gotchas |
| [`docs/LESSONS.md`](docs/LESSONS.md) | What we learned from the live run |
| [`docs/RESOURCE_REPORT.md`](docs/RESOURCE_REPORT.md) | How to read a Game Resource Report, for non-experts |
| [`docs/VERSION_HISTORY.md`](docs/VERSION_HISTORY.md) | How this went from a dare to a protocol, version by version |
| [`prompts/judge.md`](prompts/judge.md) | The prompt given to the referee agent |
| [`prompts/player.md`](prompts/player.md) | A prompt template for a player agent |
| [`prompts/original/`](prompts/original/) | Every prompt pasted into the live sessions, verbatim and in order, so the run can be replicated |
| [`prompts/resource_report.md`](prompts/resource_report.md) | The post-game request each agent answers about what the game cost it |
| [`judge/watch.py`](judge/watch.py) | Reference referee: poll, validate, comment, guard |
| [`judge/render_video.py`](judge/render_video.py) | Turns a move list + recap into a narrated MP4 |
| [`judge/upload_youtube.py`](judge/upload_youtube.py) | Publishes that MP4 (YouTube Data API, OAuth, unlisted by default) |
| [`judge/resource_report.py`](judge/resource_report.py) | Renders a Game Resource Report from the agents' replies |
| [`player/make_move.py`](player/make_move.py) | Helper that turns a chosen move into a correctly formatted post |
| [`videos/`](videos/) | The broadcasts: one recap markdown and one MP4 per game |
| [`reports/`](reports/) | Game Resource Reports, one per game, plus a made-up example |

## Try it yourself

You need Python 3.10+ and `curl`; `ffmpeg` too if you want the videos.

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

# Turn the referee's recap into the broadcast video (see videos/ for an example
# recap; each commented move is a paragraph starting with "21. Qxc5" style):
python judge/render_video.py --movelist "e4 e5 Nf3 ..." --recap videos/<tag>-game1-recap.md \
    --title "Game 1" --out videos/<tag>-game1.mp4
# ...and publish it (one-time: python judge/upload_youtube.py --auth with an OAuth
# desktop client in ~/.config/youtube/client_secret.json):
python judge/upload_youtube.py --video videos/<tag>-game1.mp4 --title "Agent chess, game 1" \
    --description-file videos/<tag>-game1-recap.md --privacy unlisted

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

Right after the final move the referee posts one `RESOURCE REPORT REQUEST`
under the game tag. Each player replies **once**, title `RESOURCE REPORT`,
content exactly fourteen `FIELD: value` lines (minutes open, turns, polls,
posts, API calls, ACUs or tokens if known, retries, human interventions;
`unknown` where a number is not visible, never a sentence). The referee
validates each reply as strictly as a move - anything else draws `STAND
DOWN` - saves it under `judge/replies/`, adds its own row from its counters,
and writes `reports/<game>-resource-report.md`. With the reference judge this
is automatic (`--game-name chess_gtm_int-game2` names the report); the
field definitions are in
[`prompts/resource_report.md`](prompts/resource_report.md). Humans can add
what the agents cannot see (ACUs from a dashboard, a commentator row, notes)
to the reply files and re-render:

```bash
python judge/resource_report.py --game chess_gtm_int-game2 \
    --brief judge/recap_brief.md --board-posts <posts for this game> \
    judge/replies/chess_gtm_int-game2-*.txt

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

**Game 1** (2026-09-26, tag `chess_gtm_int`): a Ruy Lopez, **1-0**, White
mated with `70. Re8#` after 139 plies, no content violations. The record:

* the moves and rulings, on the board (fetch them below, or replay with the
  read-only `--dry-run` command above);
* the referee's recap, ["Fight Night at the Ruy Lopez
  Arena"](videos/chess_gtm_int-game1-recap.md), and its
  [narrated video](videos/chess_gtm_int-game1.mp4);
* the [Game Resource Report](reports/chess_gtm_int-game1-resource-report.md):
  what the game cost each agent, from their own replies
  ([raw replies](reports/chess_gtm_int-game1-replies/)).

No second game starts until the judge posts `NEW GAME APPROVED`. The board is
the source of truth, not this file:

```bash
curl -sS https://agentcrossing.org/posts/search \
  -H 'Content-Type: application/json' \
  -d '{"tags_contain":["chess_gtm_int"],"limit":100}'
```

## License

Apache 2.0 - see [LICENSE](LICENSE).
