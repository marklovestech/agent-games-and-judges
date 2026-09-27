# Broadcasts

One pair of files per game: `<tag>-game<n>-recap.md` (the referee's recap,
which doubles as the video script and the YouTube description) and
`<tag>-game<n>.mp4` (rendered from it by `judge/render_video.py`).

| Game | Recap | Video | YouTube |
| --- | --- | --- | --- |
| `chess_gtm_int` game 1, moves 1-62 (game still in progress when rendered) | [recap](chess_gtm_int-game1-recap.md) | [mp4](chess_gtm_int-game1.mp4) | pending |

Rendering notes: 1280x720, one still per ply, moves the recap does not
discuss are held for 1.6 s in silence, spoken moves last as long as the
voiceover. Voice is `edge-tts` `en-US-GuyNeural` by default; `--tts espeak`
works offline. A 124-ply game with 30 commented moves runs about ten
minutes and 12 MB.
