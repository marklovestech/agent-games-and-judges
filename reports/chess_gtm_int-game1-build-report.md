# Build Resource Report: what it cost to make Game 1 possible

The [Game Resource Report](chess_gtm_int-game1-resource-report.md) covers the
four agents that played, refereed and narrated game 1. This companion report
covers a fifth agent that never touched the board: the one that built this
repository while the game was being played. Game 1 was special because
everything here (the referee program, the player helper, the prompts, the
recap, the video pipeline, the resource-report tool, the documentation) was
written during the game. Later games will not pay this cost again, so it is
kept in its own file rather than mixed into the per-game numbers.

Numbers are self-reported by the build agent from its own session, with the
compute figures read from the session's usage header by the human operator.
`unknown` means the platform did not expose a number; nothing is estimated
where a real figure was unavailable. `~` marks the agent's own estimate.

## Who took part

| Role | What it did | Reply |
| --- | --- | --- |
| Build agent (parent session) | Read the referee's session, wrote the code and docs, opened and iterated 20 pull requests, wrote the recap, rendered the videos, filed the follow-up issues, ran the security scan, wrote the PRD | this file |
| Report-writer (child session) | Spun up by the build agent with one job: design the post-game resource report (request template, renderer, reader's guide); 3 pull requests | this file |

Neither agent posted on the board. The build agent registered one board
account (`repo_overseer`) and used it once, to send the site admin a support
request asking for a reputation grant when both players ran dry.

## What each agent used

| Measure | Build agent | Report-writer (child) |
| --- | --- | --- |
| Wall-clock minutes | ~115 for the game-1 work (first commit 16:52 to the last merge at 18:41 local time); the compute figures below also cover the later protocol, hardening and PRD work | ~15 |
| Active minutes | unknown | unknown |
| Turns | unknown (not exposed; several hundred tool calls) | unknown |
| Human messages received | 31 | 1 (the kickoff prompt) |
| Pull requests opened | 20 | 3 (all merged) |
| Board posts | 0 | 0 |
| Board API calls | ~30 (read-only history fetches for dry runs, one signup, one support request, one `/me`) | 0 |
| ACUs | 64.06 | 8.02 |
| Estimated cost at $2.50/ACU | $160.15 | $20.05 |
| Tokens | unknown | unknown |
| Tools installed | python-chess, cairosvg, pillow, edge-tts, ffmpeg, ruff, google-api-python-client | none beyond Python |
| Retries | ~3 (a failed `espeak` smoke test, a failed message to another session, a movelist typo in a smoke test) | unknown |
| Human interventions | ~12 (see below) | 0 |
| Automated review rounds answered | ~15 (roughly 35 findings fixed, 4 answered and left as designed) | 3 |

## Totals

| Measure | Build (both agents) | Game (four agents) | Everything |
| --- | --- | --- | --- |
| ACUs | 72.08 | 51.27 (commentator unknown) | ~123.4 |
| Estimated cost at $2.50/ACU | $180.20 | $128.18 | ~$308 |
| Wall-clock minutes | ~115 | ~256 across three agents; ~110 on the clock | about two hours side by side |
| Pull requests | 23 | 0 | 23 |
| Board posts | 0 | 143 | 145 including a bystander's two |

So the tooling that made the game watchable, reproducible and documented
cost about 1.4 times the game itself: roughly $180 of scaffolding for a $128
game, about $308 all in. That is the single most useful thing in this
report: for a first experiment, expect to spend at least as much on the
scaffolding as on the experiment.

## What the human did (the interventions)

Every one of these was a moment where the person running the experiment had
to decide something the agent could not, or should not, decide alone:

1. Pointed the build agent at the referee's session and the empty repository.
2. Asked whether the README was up to date, then chose to make Status point
   at the live board instead of listing moves.
3. Asked whether the stalled players could upvote each other (they could not:
   upvoting needs 5 reputation and they had 0).
4. Reviewed the exact support-request text before it was sent to the admin,
   then chose which account should send it.
5. Decided that an unthreaded move should be a warning, not a rejection.
6. Pasted the three original kickoff prompts for the historical record.
7. Asked for the spicy post-game commentary and the rule that no new game
   starts without the referee's permission.
8. Asked what happens when players ignore `STAND DOWN`, which led to the
   human-triggered escalation command (no automatic bans).
9. Asked for the narrated video and a YouTube upload, later chose to skip the
   upload rather than set up OAuth credentials.
10. Asked for the resource report, in a separate agent, in an educator's voice.
11. Relayed the resource-report request into the three game sessions by hand
    and pasted the replies back (agents in this setup cannot message each
    other's sessions).
12. Approved the security scan and merged each pull request.

None of these took long. Most were a sentence. But the shape matters: the
agent did the typing, the human did the choosing.

## What that works out to

- 72.08 ACUs, about $180, bought roughly 2,000 lines of Python, 2,000 lines
  of Markdown (prompts, protocol, safety model, lessons, version history,
  PRD, this report), one 14-minute narrated video, a board-based protocol
  for the agents to report their own costs, and 23 pull requests.
- About 3.1 ACUs, or $8, per pull request, review rounds included.
- The child session cost 8.02 ACUs for a self-contained feature (template,
  renderer, reader's guide, three review rounds). Handing a well-bounded job
  to a second agent was cheap and ran in parallel with the video work.
- Roughly a third of the build agent's pull requests existed only to answer
  automated review findings on earlier ones. That is not waste; it is where
  the referee's pagination, `STAND DOWN` and approval-gate bugs were caught.
  But it is a real cost, and it is invisible if you only count features.

## Caveats

- Turns and tokens are `unknown` for both agents: the platform reports ACUs
  and message counts, not steps or tokens.
- The ~115 wall-clock minutes stop at the last merge of the game-1 work; the
  security scan, the resource-exchange protocol, the PRD and this report came
  after and are not counted in minutes, though their compute is in the ACUs.
- Dollar figures assume a flat $2.50 per ACU. They are estimates, not an
  invoice.
- The build agent's ACUs include writing the game recap and rendering both
  videos, which is why the commentator row in the game report is `unknown`:
  the same session did both jobs and cannot split the bill.
- The estimate of "several hundred tool calls" is from the agent's own
  recollection, not a counter.
