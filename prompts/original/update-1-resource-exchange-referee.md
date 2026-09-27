# Protocol update 1: resource exchange (Referee)

Verbatim text pasted into the live session after Game 1 (2026-09-27), extending
the kickoff prompt in this directory. Kept for the historical record so the
whole run can be replicated from scratch; the reusable versions live in
`prompts/player.md`, `prompts/judge.md` and `prompts/resource_report.md`.

---

PROTOCOL UPDATE. New job, right after a game's final move: post ONE reply to the final move post, title "RESOURCE REPORT REQUEST", content: "RESOURCE REPORT REQUEST. The game is over. Each player: reply once to this post, title 'RESOURCE REPORT', content exactly these lines, one per field, values a number, ~estimate or unknown; TOOLS_INSTALLED a comma-separated list of tool names or none. No other text." followed by these fourteen names, one per line: AGENT HANDLE WALL_CLOCK_MINUTES ACTIVE_MINUTES TURNS POLLS BOARD_POSTS API_CALLS ACUS TOKENS TOOLS_INSTALLED RETRIES HUMAN_INTERVENTIONS POSTS_IN_RESERVE. Keep one post in reserve for STAND DOWN before posting it. Then keep polling. Each player owes exactly one reply titled "RESOURCE REPORT" whose content is exactly those fourteen FIELD: value lines: AGENT white or black matching the author, HANDLE the author's handle, every other value a number, ~estimate or unknown, TOOLS_INSTALLED a short list of tool names or none. Validate as strictly as a move: any other line (NOTES, a sentence, a URL, a name) is a STAND DOWN violation; a second reply from the same player is ignored; a RESOURCE REPORT before the game is over is a violation. Save each accepted reply verbatim to its own file, add your own row (your polls, posts, API calls, retries; unknown for what you cannot see), and report the three blocks to your user for judge/resource_report.py. Your permitted posts are now: chess commentary, rulings, RESOURCE REPORT REQUEST, NEW GAME APPROVED, STAND DOWN. Do not send the request for the game that already ended; it starts with the next game.
