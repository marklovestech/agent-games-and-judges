# Broadcasts

One pair of files per game: `<tag>-game<n>-recap.md` (the referee's recap,
which doubles as the video script and the YouTube description) and
`<tag>-game<n>.mp4` (rendered from it by `judge/render_video.py`).

| Game | Recap | Video | YouTube |
| --- | --- | --- | --- |
| `chess_gtm_int` game 1, Ruy Lopez, 1-0 in 70 moves | [recap](chess_gtm_int-game1-recap.md) | [mp4](chess_gtm_int-game1.mp4) | not published |

Rendering notes: 1280x720, one still per ply, moves the recap does not
discuss are held for 1.6 s in silence, spoken moves last as long as the
voiceover. Voice is `edge-tts` `en-US-GuyNeural` by default; `--tts espeak`
works offline. The 139-ply game 1 with about 45 commented moves runs
roughly fourteen minutes and 16 MB.
