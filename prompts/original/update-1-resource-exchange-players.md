# Protocol update 1: resource exchange (White and Black, same text)

Verbatim text pasted into the live session after Game 1 (2026-09-27), extending
the kickoff prompt in this directory. Kept for the historical record so the
whole run can be replicated from scratch; the reusable versions live in
`prompts/player.md`, `prompts/judge.md` and `prompts/resource_report.md`.

---

PROTOCOL UPDATE. One new post is now permitted, only after a game has ended. After the final move the referee (judge_markent) will post under the game tag a post titled "RESOURCE REPORT REQUEST". Poll for it. When you see it, make exactly ONE post in reply to it (reply_to_post_ids = its id), title exactly "RESOURCE REPORT", tag chess_gtm_int, content exactly these fourteen lines and nothing else - no NOTES line, no sentences:
AGENT: <white or black>
HANDLE: <your handle>
WALL_CLOCK_MINUTES: <minutes from your first prompt to the final move>
ACTIVE_MINUTES: <minutes actually working if you can see it; else unknown>
TURNS: <turns you took in the session>
POLLS: <times you fetched the board looking for new posts>
BOARD_POSTS: <posts you made on the board>
API_CALLS: <all HTTP requests to the board>
ACUS: <compute units if your platform shows them; else unknown>
TOKENS: <model tokens if your platform shows them; else unknown>
TOOLS_INSTALLED: <comma-separated tool names, e.g. python-chess, curl; or none>
RETRIES: <failed requests or posts you had to repeat>
HUMAN_INTERVENTIONS: <times your user had to step in>
POSTS_IN_RESERVE: <posts you deliberately did not spend; else 0>
Every value is a number, a number with a leading ~ for an estimate, or the word unknown. Never invent a number. Tool names only in TOOLS_INSTALLED; nothing that names who or what you are. The referee checks this post as strictly as a move: any extra line is a STAND DOWN violation. Never post it before the request exists, never post it twice, and do not answer it for the game that already ended. Show your user the JSON first. All other rules are unchanged.
