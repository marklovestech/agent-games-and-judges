# Product Requirements Document: Agent Games and Judges

Status: describes the product as implemented at the time of writing (Game 1
complete, board-based resource exchange in place). Written for
[issue #16](https://github.com/marklovestech/agent-games-and-judges/issues/16).
Each requirement is tagged:

- **[implemented]** — in the repository and exercised in the live run;
- **[manual]** — works, but a human performs or triggers the step;
- **[optional]** — tooling present, not used in the live run;
- **[deferred]** — explicitly not done; tracked elsewhere.

## 1. Problem and purpose

Three independent AI coding agents, each in its own isolated session with no
shared memory, filesystem, or messaging channel, need to cooperate on a
long-running task (a full chess game) using only a public, permanent,
world-readable message board. The repository turns that one-off experiment
into something others can read, reproduce, and learn from: a protocol that
strangers' agents can follow, a referee that enforces it mechanically, a
safety model for posting in public, and plain-language reporting of what
the whole thing cost.

## 2. Audience

| Reader | Needs |
|---|---|
| People learning how agents coordinate | Architecture, protocol, lessons learned |
| Educators and non-expert adults | Resource reports and the recap/video, no jargon |
| Developers reproducing the run | Verbatim prompts, reference judge, player helper, setup steps |
| Operators running a referee | CLI, restart/replay behaviour, STAND DOWN and escalation workflow |

## 3. Goals and non-goals

Goals: a machine-checkable communication protocol; a referee that validates
every move and every post; strict public-content rules; a documented,
reproducible history; post-game outputs (recap, narrated video, resource
report) that a general reader can enjoy; a hard gate on starting new games.

Non-goals: strong chess play (players may use any engine or none); private
agent-to-agent messaging (unavailable, see §14); automatic punishment of
misbehaving agents; publishing to social platforms (skipped, §12).

## 4. Architecture **[implemented]**

```
white player  --posts-->  agentcrossing.org (public board, tag chess_gtm_int)  <--reads/posts--  judge
black player  --posts-->             ^                                          (referee, guard,
                                     |  reads only                              commentator, gatekeeper)
                                  bystanders
```

- Three roles: White (`white_gtm`), Black (`black_internet`), referee
  (`judge_markent`). Each is a separate agent session; each signs up for
  its own board account and bearer token.
- The board is the only shared channel. Posts are immutable and public.
  Game membership is by tag (`[a-z0-9_-]{2,15}`); Game 1 uses
  `chess_gtm_int` because the originally chosen tag was too long.
- Board economics shape the design: 0.2 reputation per post from a
  starting balance of 1.0, 5 posts/minute, upvotes need 5 reputation.
  See `docs/AGENTCROSSING.md`.

## 5. Move protocol **[implemented]**

Player post content is exactly three lines, labels at column 0:

```
MOVE: <SAN>
FEN: <FEN after the move>
MOVELIST: <full game in SAN from move 1>
```

Title is generic (`chess game - move <n>`), tag is the game tag, and the
post replies to the opponent's previous move post. White posts first.
Full contract: `docs/PROTOCOL.md`.

## 6. Referee (`judge/watch.py`) **[implemented]**

Polls the board and, for every unseen post under the tag or by either
player:

- **Chess validation** with `python-chess`: SAN legal in the prior
  position, FEN matches, MOVELIST is the whole game so far, correct side
  to move, correct author for that colour. Failures draw a public ruling.
- **Terminal state**: detects mate/stalemate/draw, logs the result, writes
  `recap_brief.md` (per-move facts for the recap), refuses further moves.
- **Content guard**: any player post that is not a valid move post (or,
  after the game, a valid `RESOURCE REPORT`) — wrong format, wrong tag,
  free text — triggers `STAND DOWN` (§8).
- **Bounded, complete reads**: paginates every search to the end, treats a
  repeated cursor or more than `--max-posts` items as a failed read and
  skips the cycle; fetches only posts newer than the last processed id,
  advancing that watermark only after a clean cycle.
- **Sparse commentary**: a short chess-only comment on genuinely
  interesting plies, keeping one post in reserve for `STAND DOWN`.
- **Post-game duties**: resource request (§10) and new-game gate (§11).

## 7. Players **[implemented]**

Defined by `prompts/player.md`, helped by `player/make_move.py` (validates a
move locally, prints the exact three-line content and the JSON request body;
never posts). Players: post moves only, validate incoming and outgoing
moves locally, poll for the opponent's reply, stop immediately on
`STAND DOWN`, reply exactly once to a `RESOURCE REPORT REQUEST`, and never
open a game without `NEW GAME APPROVED`. Every post's JSON is shown to
the human first.

## 8. Safety model and STAND DOWN **[implemented]**

`docs/SAFETY.md` is normative. In brief:

- Nothing on the board may identify the AI system, vendor, platform,
  company, person, repository, URL, hostname, file path, credential, or
  anything from a prior session. Titles stay generic.
- Players post moves only; the single exception is the fixed-format
  resource reply. The referee posts rulings, sparse commentary,
  `RESOURCE REPORT REQUEST`, `NEW GAME APPROVED`, and `STAND DOWN` only.
- Tokens live in `~/.config/agentcrossing/token.txt` (mode 600), are never
  committed or printed.
- **STAND DOWN**: the referee replies to the offending post with the fixed
  notice; all players stop; the referee posts nothing further until a human
  runs `--resume`. Every player post after the notice is recorded as
  defiance.
- **Escalation [manual]**: `--escalate` prints and sends a support request
  to the site admin asking to suspend the defiant handles. Only a human
  triggers it; there is no automatic banning.

## 9. Post-game recap **[implemented, referee-authored]**

The referee agent (job 4 in `prompts/judge.md`) writes a themed,
sports-broadcast-style recap from `recap_brief.md`: a theme per game,
performance nicknames for pieces, every move evaluated with chess
reasoning, awards. Saved under `videos/<tag>-game<n>-recap.md`; chess
content only.

## 10. Resource report exchange **[implemented]**

Right after the final move the referee posts one `RESOURCE REPORT REQUEST`
(reply to the final move). Each player replies once, title
`RESOURCE REPORT`, content exactly these fourteen `FIELD: value` lines:

```
AGENT HANDLE WALL_CLOCK_MINUTES ACTIVE_MINUTES TURNS POLLS BOARD_POSTS
API_CALLS ACUS TOKENS TOOLS_INSTALLED RETRIES HUMAN_INTERVENTIONS POSTS_IN_RESERVE
```

Values are a number, `~estimate`, or `unknown`; `TOOLS_INSTALLED` is `none`
or up to six package-style names. The judge validates as strictly as a
move (all fields present, no extras, `AGENT`/`HANDLE` match the author,
reply threaded to *its* request, one per player); anything else is
`STAND DOWN`, duplicates are ignored. Accepted replies are saved verbatim
under `judge/replies/<game>-<role>.txt`, the referee's own row is added,
and `judge/resource_report.py` renders
`reports/<game>-resource-report.md` in an educator's voice
(`docs/RESOURCE_REPORT.md` explains how to read it).

**[manual]** ACUs: agents cannot see their own compute usage, so they
report `unknown`; the human copies the session-header figure into the saved
reply file and re-renders. Game 1's exchange was fully human-mediated (the
request was pasted into each session) because the protocol did not exist
yet; the paste-ins are archived in `prompts/original/`.

## 11. New-game gate **[implemented]**

No game may start after a finished one until the referee posts
`NEW GAME APPROVED` as a reply to the final move. Only a human triggers it
(`--approve-new-game <final move id>`); the judge refuses while a
`STAND DOWN` is in force or the finished game's resource request has not
gone out, and treats an approval from any other account as void.

## 12. Narrated video **[implemented]** and YouTube **[optional, unused]**

`judge/render_video.py` turns the final MOVELIST and recap into an MP4:
board frames per move, captions, TTS voiceover (Edge TTS by default,
`espeak-ng` fallback), `ffmpeg` required. Game 1's video is committed as
`videos/chess_gtm_int-game1.mp4`. `judge/upload_youtube.py` (YouTube Data
API v3, OAuth desktop flow, unlisted upload) is present and untested against
a live channel: the owner chose to skip publishing.

## 13. Lifecycle and operations

1. Setup: `pip install -r requirements.txt`; each agent signs up and stores
   its token.
2. Kickoff: the three prompts (`prompts/*.md`; verbatim historical versions
   in `prompts/original/`) are pasted into three sessions.
3. Game: White opens, moves alternate as reply posts, judge validates.
4. End: judge logs the result, writes `recap_brief.md`, posts the resource
   request; players reply; report renders.
5. Referee agent writes the recap; operator renders the video.
6. Human runs `--approve-new-game`; next game.

CLI (all commands take `--tag --white --black`):

| Flag | Effect |
|---|---|
| (none) | watch live, post rulings/commentary/request |
| `--handle H` | judge handle to sign up / post as |
| `--dry-run --once` | one cycle, print everything, send nothing, save nothing |
| `--interval`, `--max-posts` | poll period; per-search read bound |
| `--game-name NAME` | report/reply file name (default `<tag>-game<n>`, n counted from approvals) |
| `--state PATH`, `--fresh` | state file; ignore it and replay from the start |
| `--resume` | human cleared a STAND DOWN |
| `--approve-new-game ID` | post `NEW GAME APPROVED` |
| `--escalate` | send the admin suspension request |

Persistence: `state.json` holds seen/handled post ids, the STAND DOWN
notice, defiant posts, the resource request and replies, and the final
move awaiting a request. The game itself is always rebuilt from the board;
already-handled posts replay silently and one-shot commands replay
read-only. Repository has no CI; `ruff check` and `ruff format --check`
are the lint gate.

## 14. Known limitations

- Direct session-to-session messaging returned HTTP 403; the board is the
  only channel, so every coordination message costs reputation and is public.
- Agents cannot read their own ACU/token totals (`unknown` by design).
- Moderation is manual: STAND DOWN silences the referee, not the players.
- Titles and extra tags on player posts are not validated as content is
  (open finding from the security scan; not remediated).
- Polling intervals and backoff are fixed; tuning is
  [issue #21](https://github.com/marklovestech/agent-games-and-judges/issues/21) **[deferred]**.
- Multi-game restart edge cases in the resource exchange are handled by id
  ordering, not a full chronological rebuild.

## 15. Game 1 outcome

Ruy Lopez, 1-0, 139 plies, `70. Re8#`. No illegal moves, no content
violations, one bystander thread ignored. Artifacts:
`videos/chess_gtm_int-game1-recap.md`, `videos/chess_gtm_int-game1.mp4`,
`reports/chess_gtm_int-game1-resource-report.md` (~51 ACUs across three
agents), `reports/chess_gtm_int-game1-build-report.md` (~90 ACUs, about $224, to build
this repository). `docs/VERSION_HISTORY.md` tells the story version by
version; `docs/LESSONS.md` lists what went wrong and what we changed.
