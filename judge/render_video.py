#!/usr/bin/env python3
"""Turn a finished game plus the referee's recap into a narrated MP4.

Input is the move list (SAN, from move 1) and the recap the referee wrote
(markdown). The recap is split into segments: everything before the first
move-tagged paragraph is the intro (spoken over the starting position);
a paragraph that starts with a move token such as `12. Nf3`, `12... Bb4`,
`**12. Nf3**` or `12.Nf3:` (with the text on the same paragraph or in the
paragraphs that follow) is spoken over the position after that move; and
everything after a markdown heading that comes after the first tagged move
is the outro (final position). Moves the recap does not mention are shown
briefly in silence.

    python judge/render_video.py --movelist "e4 e5 Nf3 ..." --recap recap.md \
        --title "Game 1" --out videos/game-1.mp4

Needs ffmpeg on PATH, and one of: edge-tts (default, neural voices, needs
network) or espeak-ng (`--tts espeak`, offline). Everything in the output
is chess content plus whatever the recap says; keep the recap chess-only.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cairosvg
import chess
import chess.svg
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1280, 720
BOARD = 640
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"
FONT_REG = FONT_DIR / "DejaVuSans.ttf"
BG = (24, 26, 32)
FG = (235, 235, 235)
DIM = (150, 155, 165)
SILENT_HOLD = 1.6  # seconds shown for a move the recap does not talk about

# `12. Nf3`, `12... Bb4`, `**12. Nf3**`, `12.Nf3:` — leading markdown emphasis and list bullets allowed.
MOVE_TOKEN = re.compile(
    r"^\W{0,4}(\d+)\s*(\.\.\.|\.)\s*([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?[+#]?)"
)


@dataclass
class Segment:
    ply: int  # 0 = start position, n = position after ply n
    text: str  # spoken and captioned; "" = silent hold
    announce: bool = True  # prefix the narration with "White plays ..."


def parse_recap(recap: str, moves: list[str]) -> list[Segment]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", recap) if p.strip()]
    tagged: dict[int, list[str]] = {}
    intro: list[str] = []
    outro: list[str] = []
    current: int | None = None  # ply the following untagged paragraphs belong to
    in_outro = False
    for p in paras:
        if p.startswith("#"):
            if current is not None:
                in_outro = True
            continue
        m = MOVE_TOKEN.match(p)
        if m and not in_outro:
            number, dots, san = int(m.group(1)), m.group(2), m.group(3)
            ply = number * 2 - (1 if dots == "." else 0)
            if 1 <= ply <= len(moves) and moves[ply - 1].rstrip("+#") == san.rstrip("+#"):
                current = ply
                tagged.setdefault(ply, []).append(clean(p[m.end() :]))
                continue
            print(f"warning: paragraph looks move-tagged but does not match the game: {p[:60]!r}", file=sys.stderr)
        if in_outro:
            outro.append(clean(p))
        elif current is None:
            intro.append(clean(p))
        else:
            tagged[current].append(clean(p))
    segments = [Segment(0, " ".join(intro), announce=False)]
    for ply in range(1, len(moves) + 1):
        segments.append(Segment(ply, " ".join(tagged.get(ply, []))))
    if outro:
        segments.append(Segment(len(moves), " ".join(outro), announce=False))
    return segments


PIECE_NAMES = {"K": "King", "Q": "Queen", "R": "Rook", "B": "Bishop", "N": "Knight"}


def spoken_san(san: str) -> str:
    """'Nxe5+' -> 'Knight takes e5, check'; 'O-O' -> 'castles short'."""
    suffix = ""
    if san.endswith("#"):
        suffix, san = ", checkmate", san[:-1]
    elif san.endswith("+"):
        suffix, san = ", check", san[:-1]
    if san.startswith("O-O"):
        return ("castles long" if san == "O-O-O" else "castles short") + suffix
    promo = ""
    if "=" in san:
        san, piece = san.split("=")
        promo = f", promotes to {PIECE_NAMES[piece]}"
    words = []
    if san[0] in PIECE_NAMES:
        words.append(PIECE_NAMES[san[0]])
        san = san[1:]
    if "x" in san:
        origin, dest = san.split("x")
        if origin:
            words.append(origin)
        words += ["takes", dest]
    else:
        words.append(san)
    return " ".join(words) + promo + suffix


def clean(p: str) -> str:
    p = re.sub(r"[*_`>]+", "", p)
    p = re.sub(r"^\s*[-•]\s*", "", p, flags=re.MULTILINE)
    return " ".join(p.split())


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def frame(board: chess.Board, last: chess.Move | None, title: str, move_label: str, caption: str, out: Path) -> None:
    svg = chess.svg.board(
        board,
        lastmove=last,
        check=board.king(board.turn) if board.is_check() else None,
        size=BOARD,
        coordinates=True,
    )
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=BOARD, output_height=BOARD)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    board_img = Image.open(io.BytesIO(png)).convert("RGBA")
    img.paste(board_img, (40, (HEIGHT - BOARD) // 2), board_img)
    d = ImageDraw.Draw(img)
    x = 40 + BOARD + 40
    w = WIDTH - x - 40
    size = 34
    while size > 18 and d.textlength(title, font=font(FONT_BOLD, size)) > w:
        size -= 2
    title_lines = wrap(d, title, font(FONT_BOLD, size), w)[:2]
    y = 44
    for line in title_lines:
        d.text((x, y), line, font=font(FONT_BOLD, size), fill=FG)
        y += size + 6
    d.text((x, y + 8), move_label, font=font(FONT_REG, 26), fill=DIM)
    y += 62
    size = 26
    while size >= 16:
        fnt = font(FONT_REG, size)
        lines = wrap(d, caption, fnt, w)
        if y + len(lines) * (size + 8) <= HEIGHT - 40:
            break
        size -= 2
    for line in lines:
        d.text((x, y), line, font=fnt, fill=FG)
        y += size + 8
    img.save(out)


def tts(text: str, out: Path, engine: str, voice: str) -> None:
    if engine == "edge":
        import edge_tts

        async def run() -> None:
            await edge_tts.Communicate(text, voice).save(str(out))

        asyncio.run(run())
    elif engine == "espeak":
        wav = out.with_suffix(".wav")
        subprocess.run(["espeak-ng", "-s", "165", "-w", str(wav), text], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), str(out)], check=True)
    else:
        raise SystemExit(f"unknown tts engine {engine}")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def clip(image: Path, audio: Path | None, seconds: float, out: Path) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "24", "-i", str(image)]
    if audio:
        cmd += ["-i", str(audio)]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono"]
    cmd += [
        "-t",
        f"{seconds:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-ar",
        "24000",
        "-ac",
        "1",
        "-b:a",
        "96k",
        "-shortest",
        str(out),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--movelist", required=True, help="full game in SAN from move 1, space separated")
    ap.add_argument("--recap", type=Path, required=True, help="the referee's recap (markdown)")
    ap.add_argument("--title", default="Chess game", help="shown on every frame; keep it chess-only")
    ap.add_argument("--out", type=Path, required=True, help="output .mp4")
    ap.add_argument("--tts", choices=["edge", "espeak"], default="edge")
    ap.add_argument("--voice", default="en-US-GuyNeural", help="edge-tts voice name")
    ap.add_argument("--pause", type=float, default=0.6, help="seconds of silence after each spoken segment")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found on PATH")
    moves = args.movelist.split()
    board = chess.Board()
    positions: list[tuple[chess.Board, chess.Move | None]] = [(board.copy(), None)]
    for san in moves:
        try:
            mv = board.push_san(san)
        except ValueError as e:
            raise SystemExit(f"illegal move in movelist: {san}: {e}")
        positions.append((board.copy(), mv))
    segments = parse_recap(args.recap.read_text(), moves)
    spoken = sum(1 for s in segments if s.text)
    print(f"{len(moves)} plies, {len(segments)} segments, {spoken} spoken", file=sys.stderr)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        clips = []
        for i, seg in enumerate(segments):
            pos, last = positions[seg.ply]
            if seg.ply == 0:
                label = "Starting position"
            else:
                n = (seg.ply + 1) // 2
                label = f"{n}. {moves[seg.ply - 1]}" if seg.ply % 2 else f"{n}... {moves[seg.ply - 1]}"
            if pos.is_game_over():
                label += f"   {pos.result()}"
            img = tmp / f"f{i:04d}.png"
            frame(pos, last, args.title, label, seg.text, img)
            audio = None
            seconds = SILENT_HOLD
            if seg.text:
                audio = tmp / f"a{i:04d}.mp3"
                speech = seg.text
                if seg.announce:
                    side = "White" if seg.ply % 2 else "Black"
                    speech = f"{side} plays {spoken_san(moves[seg.ply - 1])}. {speech}"
                tts(speech, audio, args.tts, args.voice)
                seconds = duration(audio) + args.pause
            c = tmp / f"c{i:04d}.mp4"
            clip(img, audio, seconds, c)
            clips.append(c)
            print(f"  segment {i}: ply {seg.ply} {seconds:.1f}s", file=sys.stderr)
        concat = tmp / "concat.txt"
        concat.write_text("".join(f"file '{c}'\n" for c in clips))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-c",
                "copy",
                str(args.out),
            ],
            check=True,
        )
    print(f"wrote {args.out} ({args.out.stat().st_size // 1024} KB, {duration(args.out):.0f}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
