#!/usr/bin/env python3
"""Pack a YouTube transcript as a source of a research archive.

A video is a URL like any other. Its folder is
`<root>/data/<leaf>/sources/urls/<stem>/` and holds the transcript as the payload, a structural
markdown copy, an `index.json` and a `url.txt` record — exactly the shape a paper has. There is no
second transcript tree: `~/Transcriptions` is legacy, not a destination.

Two modes:

  --transcript PATH   pack a transcript that already exists (no GPU, no download)
  (default)           run this skill's `yt-transcribe.sh`, then pack what it produced

Examples:

  yt_archive.py --root ~/Repositories/Reserach \\
      --leaf AI/Harness/Agent_Architecture_Orchestration \\
      --url 'https://youtu.be/VIDEO_ID'

  yt_archive.py --root ~/Repositories/Reserach --leaf Medical/Clinical_AI \\
      --transcript ~/Transcriptions/Technology/talk_VIDEO_ID.txt --slug talk

Exit codes: 0 packed, 1 refused (missing input, existing folder without --force), 2 transcription
failed. The last two lines of stdout are `STEM=<stem>` and `FOLDER=<absolute path>`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TRANSCRIBE = os.path.join(HERE, "yt-transcribe.sh")

VIDEO_ID = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|live/|shorts/|embed/))([A-Za-z0-9_-]{6,})"
)


def slugify(text: str, limit: int = 60) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:limit].strip("_") or "video"


def header_value(text: str, name: str) -> str:
    match = re.search(rf"^{name}:\s*(.+)$", text, re.M)
    return match.group(1).strip() if match else ""


def strip_header(text: str) -> str:
    lines = text.splitlines()
    kept = [ln for ln in lines if not re.match(r"^(URL|Title|Transcribed|Language|Model):", ln)]
    return "\n".join(kept).strip("\n") + "\n"


def run_transcribe(url: str, language: str | None, model: str | None) -> str:
    tmp = tempfile.mkdtemp(prefix="yt-archive-")
    cmd = [TRANSCRIBE, url, "--output-dir", tmp]
    if language:
        cmd += ["--language", language]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        sys.exit(2)
    found = sorted(
        os.path.join(tmp, name) for name in os.listdir(tmp) if name.endswith(".txt")
    )
    if not found:
        sys.exit("FATAL: yt-transcribe.sh reported success but wrote no .txt")
    return found[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True, help="research root, e.g. ~/Repositories/Reserach")
    ap.add_argument("--leaf", required=True, help="taxonomy leaf, e.g. AI/Harness/Skills_Workflows")
    ap.add_argument("--url", help="canonical video URL (required unless the transcript carries one)")
    ap.add_argument("--transcript", help="pack this .txt instead of transcribing")
    ap.add_argument("--slug", help="folder slug; default from the title")
    ap.add_argument("--date", help="fetch date YYYY-MM-DD; default today")
    ap.add_argument("--summary", help="markdown summary to store as summary.md")
    ap.add_argument("--language", help="passed to yt-transcribe.sh")
    ap.add_argument("--model", help="passed to yt-transcribe.sh")
    ap.add_argument("--force", action="store_true", help="replace an existing source folder")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.root))
    if not os.path.isdir(os.path.join(root, "data")):
        sys.exit(f"FATAL: {root} is not a research root (no data/)")

    if args.transcript:
        src = os.path.abspath(os.path.expanduser(args.transcript))
        if not os.path.isfile(src):
            sys.exit(f"FATAL: transcript not found: {src}")
        text = open(src, encoding="utf-8", errors="replace").read()
    else:
        if not args.url:
            sys.exit("FATAL: --url is required when transcribing")
        text = open(run_transcribe(args.url, args.language, args.model), encoding="utf-8", errors="replace").read()

    url = args.url or header_value(text, "URL")
    if not url:
        sys.exit("FATAL: no URL given and none in the transcript header")
    match = VIDEO_ID.search(url)
    if not match:
        sys.exit(f"FATAL: cannot read a YouTube id from {url}")
    video_id = match.group(1)

    title = header_value(text, "Title") or args.slug or video_id
    slug = slugify(args.slug or title)
    date = args.date or dt.date.today().isoformat()
    stem = f"{date}_{slug}_{video_id}"
    folder = os.path.join(root, "data", args.leaf, "sources", "urls", stem)

    if os.path.isdir(folder) and not args.force:
        sys.exit(f"FATAL: {folder} exists; pass --force to replace it")
    os.makedirs(folder, exist_ok=True)

    body = strip_header(text)
    txt_path = os.path.join(folder, f"{stem}.txt")
    with open(txt_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")

    digest = hashlib.sha256(open(txt_path, "rb").read()).hexdigest()[:16]
    md_path = os.path.join(folder, f"{stem}.md")
    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            "---\n"
            f"title: {json.dumps(title, ensure_ascii=False)}\n"
            f"url: {url}\n"
            f"video_id: {video_id}\n"
            f"fetched_at: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}\n"
            f"transcript_sha256: {digest}\n"
            f"chars: {len(body)}\n"
            f"lines: {len(body.splitlines())}\n"
            "extractor: yt-whisper\n"
            "format: archive-transcript/1\n"
            "---\n\n"
            f"# {title}\n\n"
            f"> **Source:** {url} — video `{video_id}`, transcript fetched {date}\n\n"
            f"{body}"
        )

    index = {
        "format": "archive-transcript/1",
        "title": title,
        "url": url,
        "video_id": video_id,
        "fetched_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "transcript": {
            "file": f"{stem}.txt",
            "sha256": digest,
            "chars": len(body),
            "lines": len(body.splitlines()),
        },
        "extractor": "yt-whisper",
    }
    with open(os.path.join(folder, "index.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    url_txt = os.path.join(folder, "url.txt")
    if not os.path.exists(url_txt):
        with open(url_txt, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(
                "key: unregistered\n"
                f"canonical_url: {url}\n"
                "acquired_via: yt-whisper-skill/scripts/yt_archive.py\n"
                f"fetched_at: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}\n"
                "status: fetched\n"
            )

    if args.summary:
        shutil.copyfile(os.path.expanduser(args.summary), os.path.join(folder, "summary.md"))

    print(f"PACKED  {title}")
    print(f"BYTES   {len(body)} chars, sha256 {digest}")
    print(f"BATCH   yt {slug} {url} {args.leaf}")
    print(f"STEM={stem}")
    print(f"FOLDER={folder}")


if __name__ == "__main__":
    main()
