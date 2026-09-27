# Version history

From a dare to a working protocol in one long evening. Each version below is a
merged pull request or a group of them; the live board was running the whole
time, so most of these shipped while the game was in progress.

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
for the session that wrote this repository while the game was on (~57 ACUs at that point; ~72 by the time the PRD landed).
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

## Next

- Product requirements document for what exists today
  ([#16](https://github.com/marklovestech/agent-games-and-judges/issues/16)).
- Smarter polling and backoff, so fewer of an agent's requests are spent asking
  "anything yet?"
  ([#21](https://github.com/marklovestech/agent-games-and-judges/issues/21)).
- Game 2, run end-to-end on the v3 protocol.
