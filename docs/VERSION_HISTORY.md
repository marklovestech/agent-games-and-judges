# Version history

From a dare to a working protocol, a priced-out ledger and a product spec in
one long evening and the night that followed. Each version below is a merged
pull request or a group of them; the live board was running for most of it, so
many of these shipped while the game was in progress.

## v0 — The dare (2026-09-26, late afternoon)

Three agents, three separate sessions, no way to talk to each other except a
public message board that charges 0.2 reputation per post. Could they play a
game of chess, with a fourth agent refereeing, without ever saying anything
that was not a chess move? Three prompts were written by hand
([`prompts/original/`](../prompts/original/)) and the sessions were started.
White opened 1. e4.

## v0.1 — Five moves and a stall

Both players ran out of reputation after five posts each. The game froze at
5... Be7. Instead of giving up, the experiment gained a fourth account,
`repo_overseer`, which asked the site admin for a reputation grant. The admin
said yes. Lesson one, learned live: *on a public board the scarce resource is
not compute, it is permission to speak.*

## v1.0 — The repository (PRs #1–#3)

The improvised game became something other people could read. Protocol,
safety model, board API notes, reusable player and referee prompts, and a
reference judge (`judge/watch.py`) that replays every move with python-chess
and rules on legality, FEN, move-list continuity and turn order. The README
learned to point at the live board instead of a move list that went stale
every fifteen seconds.

## v1.1 — Hardening under review (PRs #4–#8)

Automated review found what a hurried author missed: unpaginated searches,
a STAND DOWN that could silently fail to send, a judge that would rule on a
partial view of the board, a search cursor that repeated forever and looked
like "done". Each fix made the referee more paranoid in the right way: *if you
cannot see everything, judge nothing.*

## v1.2 — The record (PR #7)

The three verbatim kickoff prompts were archived, typos and the too-long tag
included, so the first run can be reproduced exactly.

## v2.0 — A referee with a personality (PRs #9–#11)

Three ideas in one stretch:

- **The recap.** When a game ends the judge emits a facts table for every ply
  (captures, checks, material swings, blunder candidates) and the referee turns
  it into a themed, sports-desk commentary with nicknamed pieces.
- **The gate.** No new game without a `NEW GAME APPROVED` post from the
  referee, and only the referee's own account can grant it.
- **The consequence.** Players who keep posting after STAND DOWN are recorded,
  and a human can `--escalate` a suspension request to the site admin. Never
  automatic; always a person's call.

## v2.1 — Numbers people can read (PR #12)

A child session built the Game Resource Report: a fixed question block asked
of every agent, a renderer, and a reader's guide written for an average adult
rather than an AI specialist.

## v2.2 — The broadcast (PR #14)

`judge/render_video.py` turns the final move list and the recap into a
narrated MP4: board frames per move, the commentary read aloud, every move
announced. A YouTube uploader shipped alongside it (unused so far, by choice).

## v2.3 — Game 1 ends (PRs #17–#19)

**1-0, 70. Re8#, 139 plies, Ruy Lopez, no illegal moves, no violations.** The
recap and the 14-minute video were completed through the mate. The agents
answered the resource questions themselves:
[the game report](../reports/chess_gtm_int-game1-resource-report.md)
(~51 ACUs to play and referee; Black spent about four times what White did)
and, separately, [the build report](../reports/chess_gtm_int-game1-build-report.md)
for the session that wrote this repository while the game was on (~57 ACUs at that point; ~90 by the time the history was written).
A deep security scan was run on the whole repo.

## v3.0 — The agents ask each other (PR #20)

Game 1's resource report needed a human to carry questions between sessions.
Agents cannot message each other directly, but they all read the board, so the
board became the channel: after the final move the referee posts one
`RESOURCE REPORT REQUEST`; each player answers exactly once with fourteen
`FIELD: value` lines, numbers or `unknown` only, no prose; the judge validates
the reply as strictly as a move, saves it, and renders the report by itself.
The prompts the live agents received for the change are in
[`prompts/original/`](../prompts/original/) with everything else they were
ever told.

## v3.1 — The scan comes back (PRs #22, #23, #28–#30)

While the resource exchange was landing, the deep security scan finished and
handed the referee a list of ways a hostile player could get around it. The
move-post regex was a DOTALL pattern that a crafted post could make crawl, so
the judge now reads the three lines one at a time, labels at column 0, no
regex to trip. A player's **title** and **tags** had been an unguarded
free-text channel next to a strictly guarded body; now the title must be
`chess game - move <n>` naming the post's own move, the tags must be exactly
the game tag, and anything else is a STAND DOWN like any other violation. A
flood of posts under the tag could grow `state.json` without limit; the judge
now remembers only player and referee ids and prunes the rest. And every
cycle's search work is bounded to posts newer than the last one it processed,
so a busy board cannot stall the referee. *A referee that is only strict
about the part of the post you expected is not strict.*

## v3.2 — Trust, but verify the verifier (PR #24)

The resource exchange from v3.0 met its first adversary: automated review.
Six findings, then three more, then two more, across four rounds. An unsent
request was never retried; a reply did not have to be a reply to *the*
request; a partial fourteen-field block passed; a `TOOLS_INSTALLED` value
could smuggle a product name onto the public board; game 2's files would
overwrite game 1's; `--game-name` could write outside the replies folder; a
dry run erased live state; a repeated field slipped past the "all fields
present" check; a player's second report could trigger a STAND DOWN instead
of being ignored. Every one fixed, one thread left open on purpose with an
assessment for the human. No protocol change for the agents already playing.

## v3.3 — The spec (PR #25)

[`docs/PRD.md`](PRD.md): everything the product does today, each capability
tagged **[implemented]**, **[manual]**, **[optional]** or **[deferred]** so
nobody has to guess which parts a human still performs (approving a new game,
pasting ACU totals) and which parts were built but not used (the YouTube
uploader). Closed issue #16.

## v3.4 — The bill (PRs #26, #27)

ACUs became dollars. At an assumed $2.50 per ACU the renderer now prints an
estimated cost per agent, per game and per ply, with `--acu-price` to change
the rate or turn the money off. The numbers at the time:

| | ACUs | Estimate |
| --- | --- | --- |
| Game 1: play, referee, commentate | 51.27 (commentator unknown) | **$128.18**, about $0.92 per ply |
| Building this repository (parent + child session) | 72.08 | **$180.20** |
| Everything | ~123.4 | **~$308** |

So the scaffolding cost about 1.4 games. Review immediately found that
`--example` ignored the price flag and that a fractional rate printed as
`$0.00`; #27 fixed both within the hour.

## v3.5 — The final bill

With the history written and the last review round closed, the build
session's meter was read one more time: **81.61 ACUs**, plus 8.02 for the
child session, **89.63 ACUs ≈ $224.08** across 36 human messages and 29
merged pull requests. Against the game's $128.18 that puts everything at
**~140.9 ACUs ≈ $352**: the scaffolding cost about 1.75 games. The
[build report](../reports/chess_gtm_int-game1-build-report.md) carries the
final figures; the game and referee numbers never changed.

## Where things stand

Twenty-nine merged pull requests, one finished game, one narrated video, two resource
reports with prices on them, a PRD, a security scan with its medium finding
and all but one low closed, and a protocol under which the next game reports its own cost without
a human carrying messages. All of it from `1. e4`.

## Next

- The last low scan finding: cap the history fetch in `make_move --from-board`.
- Smarter polling and backoff, so fewer of an agent's requests are spent asking
  "anything yet?"
  ([#21](https://github.com/marklovestech/agent-games-and-judges/issues/21)).
- Game 2, run end-to-end on the v3 protocol.
