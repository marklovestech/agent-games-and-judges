# Game 1 resource request (White, Black and Referee, same text)

Verbatim text pasted by hand into each live session after Game 1 ended
(2026-09-27, 1-0, 70. Re8#), before the board-based exchange existed. The three
replies are in `reports/chess_gtm_int-game1-replies/`. Kept for the historical
record; the reusable template is `prompts/resource_report.md`.

---

DEMONSTRATION AND EXPERIMENTATION ONLY. The chess game you took part in is over (1-0, 70. Re8#). Before the next one starts, the referee is compiling a Game Resource Report so that ordinary people can see what it costs to run agents like us. Please report what this game cost you.

Answer here, to your user, in this session. Do NOT post any of this on the message board. The board is for chess moves only; anything else there is a violation.

Rules for your answer:
- Report only what you can read from your own session or estimate honestly. Write `unknown` where your platform does not expose a number. Do not guess a number to look complete; `unknown` is a valid, useful answer.
- Mark estimates with a `~` (for example `~40`).
- Count from the moment you first read the game prompt to the moment you sent your last game-related message to your user, including time spent waiting for the opponent.
- Say nothing about who or what you are: no AI system, vendor, product, platform, company, person, repository, URL, hostname, file path, credential or session identifier. Field names and numbers only; the NOTES line is for plain observations like "waited 40 minutes for one move".

Reply with exactly this block, one field per line, values after the colon:

AGENT: <white | black | referee>
HANDLE: <your board handle, e.g. white_gtm>
WALL_CLOCK_MINUTES: <minutes from first prompt to last game message>
ACTIVE_MINUTES: <minutes actually working, if your platform shows it; else unknown>
TURNS: <number of turns / steps you took in the session>
POLLS: <number of times you fetched the board to look for new posts>
BOARD_POSTS: <number of posts you made on the board>
API_CALLS: <total HTTP requests to the board, polls + posts + signup + /me checks>
ACUS: <Agent Compute Units consumed, if your platform reports them; else unknown>
TOKENS: <model tokens consumed, if your platform reports them; else unknown>
TOOLS_INSTALLED: <comma-separated, e.g. python-chess, curl; or none>
RETRIES: <failed requests or posts you had to repeat>
HUMAN_INTERVENTIONS: <times your user had to step in, correct, or approve>
POSTS_IN_RESERVE: <posts you deliberately did not spend, e.g. the STAND DOWN reserve; else 0>
NOTES: <one or two plain sentences, optional>

That is the whole task. Thank you.
