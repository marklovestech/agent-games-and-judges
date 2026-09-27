#!/usr/bin/env python3
"""Upload a rendered game video to YouTube (Data API v3).

One-time setup by the channel owner: create an OAuth "Desktop app" client in
Google Cloud with the YouTube Data API enabled, download its JSON to
~/.config/youtube/client_secret.json, then run this once with --auth to
complete the browser consent flow. The refresh token lands in
~/.config/youtube/token.json (chmod 600). Neither file belongs in the repo.

    python judge/upload_youtube.py --video videos/game-1.mp4 \
        --title "Agent chess, game 1: Fight Night at the Ruy Lopez" \
        --description-file videos/game-1-recap.md [--privacy unlisted] [--dry-run]

The title and description are public; keep them chess-only like everything
else in this experiment. Default privacy is unlisted so a human can check the
video before making it public.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CONFIG = Path.home() / ".config" / "youtube"
CLIENT_SECRET = CONFIG / "client_secret.json"
TOKEN = CONFIG / "token.json"
CATEGORY_GAMING = "20"


def credentials(interactive: bool) -> Credentials:
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            raise SystemExit(f"no valid token at {TOKEN}; run once with --auth")
        if not CLIENT_SECRET.exists():
            raise SystemExit(f"missing {CLIENT_SECRET} (OAuth desktop client JSON from Google Cloud)")
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=False)
        CONFIG.mkdir(parents=True, exist_ok=True)
        fd = os.open(TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(creds.to_json())
    return creds


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", type=Path, help="the .mp4 to upload")
    ap.add_argument("--title", help="public title (chess-only, max 100 chars)")
    ap.add_argument("--description-file", type=Path, help="public description, e.g. the recap markdown")
    ap.add_argument("--privacy", choices=["public", "unlisted", "private"], default="unlisted")
    ap.add_argument("--tags", default="chess", help="comma-separated YouTube tags (public; chess-only)")
    ap.add_argument("--auth", action="store_true", help="run the OAuth consent flow and store the token, then exit")
    ap.add_argument("--dry-run", action="store_true", help="print the request body and exit without uploading")
    args = ap.parse_args()

    if args.auth:
        credentials(interactive=True)
        print(f"token stored at {TOKEN}")
        return 0
    if not (args.video and args.title):
        ap.error("--video and --title are required unless --auth")
    if len(args.title) > 100:
        ap.error("YouTube titles are limited to 100 characters")
    description = args.description_file.read_text() if args.description_file else ""
    body = {
        "snippet": {
            "title": args.title,
            "description": description[:5000],
            "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
            "categoryId": CATEGORY_GAMING,
        },
        "status": {"privacyStatus": args.privacy, "selfDeclaredMadeForKids": False},
    }
    print("videos.insert body:\n" + json.dumps(body, indent=2), flush=True)
    if args.dry_run:
        print("dry-run: not uploaded")
        return 0

    youtube = build("youtube", "v3", credentials=credentials(interactive=False))
    media = MediaFileUpload(str(args.video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}%", file=sys.stderr, flush=True)
    print(f"uploaded: https://www.youtube.com/watch?v={response['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
