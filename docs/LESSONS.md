# Lessons from the live run

Running log. Newest at the bottom.

## 2026-09-26 - first game (white_gtm vs black_internet, judge_markent)

### The first bug was a validation rule, not chess

The plan said "the game tag is `chess_gtm_internet`". That is 18 characters.
AgentCrossing tags must match `[a-z0-9_-]{2,15}`. The player agent hit the
400, shortened the tag to `chess_gtm_int`, and moved on. The judge, following
its prompt literally, searched for `chess_gtm_internet`, got a 400 on every
poll, and had to notice and adapt on its own. It did - it searched both tags,
then dropped the broken one - but it cost a couple of minutes and several
restarts of its watcher.

Takeaway: **read the API's validation rules before writing the prompt**, and
give agents an explicit fallback ("if the tag is rejected, use X") rather than
hoping they converge on the same one independently. Three agents that each
invent a different fallback cannot find each other.

### Restart your background watcher carefully

The judge's first attempt to restart its poller (`pkill -f watch.py; nohup
python3 watch.py &`) killed its own shell because the `pkill` pattern matched
the shell command that contained the string `watch.py`. Second attempt used
`pgrep` first; third used `setsid nohup ... & disown`. Trivial, but it is the
kind of thing that eats a post budget's worth of time.

Takeaway: the reference `judge/watch.py` writes a pid file and is idempotent
to restart.

### Move numbers in `MOVE:`

The protocol says `MOVE: <SAN>`. White posted `MOVE: 1. e4`. Strictly that is a
violation; practically it is unambiguous. The judge accepted it. The reference
implementation strips move numbers before parsing so this never becomes a
false `STAND DOWN`.

Takeaway: when a format is going to be produced by an LLM, make the parser
tolerant of the *obvious* variants and strict about everything else.

### The players converged on a convention nobody specified

The prompts said nothing about replies. Both players independently posted each
move as a reply to the opponent's previous move, so the game is a proper
thread on the board. Good instinct - and a reminder that agents will fill any
gap in a protocol, so the *judge* must either forbid the gap-filler or accept
it explicitly. The first draft of this repo's judge treated replies as a
violation and would have issued a `STAND DOWN` on Black's `1... e5`. The
protocol now requires the reply.

Takeaway: dry-run the judge against real posts before letting it post. A
false `STAND DOWN` is permanent and stops the game.

### Budget shapes behaviour

With 1.0 reputation and 0.2 per post, a judge has four commentary posts and one
reserved `STAND DOWN`. That constraint did more to keep posts terse and
relevant than any amount of "comment sparingly" in the prompt.

### Watch the author, not just the tag

A player who posts something off-tag (or with a typo in the tag) is still a
player who posted. The judge polls each player's full history, not only the
game tag. In this run both players had clean histories.

### How the game ended

White won, 1-0, with `70. Re8#` after 139 plies and roughly 150 board posts.
Both players ran out of reputation at move 5 and the game only resumed after
a support request to the site admin for a reputation grant; the rest of the
game ran without a single content violation or illegal move. The reference
judge replayed the whole record in `--dry-run` at the end and reported the
same result the players did.

The chess itself was instructive too: the players traded queens by move 28,
swapped material back and forth in a long rook ending, and the decisive
mistakes were positional (a rook offside grabbing a pawn while a mating net
closed) rather than tactical blunders. Neither player ever posted an illegal
move, which is what python-chess on both ends buys you.

### Open questions

* Should the judge write "last processed post id" to `/me/context` so it can
  resume after a restart without re-reading the whole tag?
* Could the players and the judge agree on the tag *through the board itself*
  (e.g. the judge posts the canonical tag first)? That costs one post but
  removes the coordination problem.
* Is there a cheaper "I am alive" signal than a post? Right now silence is
  indistinguishable from a crashed agent.
