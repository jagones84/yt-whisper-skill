---
name: yt-whisper-skill
version: 1.0.0
description: Locally transcribe YouTube videos with Whisper on CUDA and pack each one as a source of a research archive at <root>/data/<leaf>/sources/urls/<stem>/ (transcript .txt, archive-transcript/1 .md, index.json, url.txt, optional summary.md); a legacy standalone output at ~/Transcriptions stays for non-archive callers. Also generates a structured summary and a research plan from any input file. Use for transcription, summary, or research-plan requests.
metadata:
  emoji: 🎥
  os: [linux, darwin, win32]
---

# yt-whisper-skill

Transcribes YouTube videos with the local `scripts/yt-transcribe.sh` and a self-contained Whisper
toolchain (its own `.venv`, created by `scripts/install.sh`). It can also turn a transcript (or any
input document) into a structured AI summary and a compact research plan.

## Features

- Download YouTube audio and transcribe it with Whisper on CUDA
- Auto-pick a faster model for long videos
- Respect `t=` / `start=` / `end=` timestamps in YouTube URLs
- Pack each video as a source folder of the research archive (`--root/--leaf`), the default when a root is known
- Legacy standalone mode: save to `~/Transcriptions/<Category>/` with a URL + title header (old callers only)
- Infer the category from the title, or force one with `--category`
- Support a single URL, several URLs, or bare 11-char video IDs
- Optional language detection or forced language
- Delete temporary media after transcription
- Produce a structured `*_AISUMMARY.md` report from a transcript
- Produce a compact `*_AISEARCHPLAN.md` research plan from ANY input file

## Quick Start

```bash
# One-time setup (creates the local venv and installs yt-dlp + whisper)
bash {baseDir}/scripts/install.sh

# Transcribe a single video
{baseDir}/scripts/yt-transcribe.sh "https://youtu.be/VIDEO_ID"

# Several videos in one run
{baseDir}/scripts/yt-transcribe.sh "https://youtu.be/ID1" "https://youtu.be/ID2"

# Force a language, or force a category
{baseDir}/scripts/yt-transcribe.sh "https://youtu.be/VIDEO_ID" --language it
{baseDir}/scripts/yt-transcribe.sh "https://youtu.be/VIDEO_ID" --category Philosophy

# Live URL with a timestamp is normalized, the time range is preserved
{baseDir}/scripts/yt-transcribe.sh "https://www.youtube.com/live/VIDEO_ID?t=276s"
```

If `install.sh` has been run, the same script is also available on PATH as `yt-transcribe`.

## Requirements

- `ffmpeg` on PATH
- the local venv at `{baseDir}/.venv` (created by `scripts/install.sh`; holds `yt-dlp` and
  `openai-whisper`)
- a JavaScript runtime for `yt-dlp` (`node`, `deno`, `bun` or `quickjs`)
  - YouTube requires one; the script auto-resolves it from PATH and the usual install locations
    (`~/.local/bin`, `~/.nvm/versions/node/*`, `~/.deno/bin`, `/usr/bin`, ...) and passes the
    concrete path as `--js-runtimes <name>:<path>`
  - **symptom when missing:** `HTTP Error 403: Forbidden` — this is NOT a YouTube block and NOT a
    yt-dlp bug, it means no JS runtime was found

## Output Format

Two destinations, one skill.

**Archive mode (default when a research root is known).** A video is a URL like any other: pack it as
a source of the archive.

```bash
{baseDir}/scripts/yt_archive.py --root <R> --leaf <domain>/<leaf> --url '<full youtube url>'
{baseDir}/scripts/yt_archive.py --root <R> --leaf <domain>/<leaf> --transcript <file.txt> --slug <slug>
```

It transcribes (or takes `--transcript`, without download or GPU), then writes one folder
`<R>/data/<leaf>/sources/urls/<date>_<slug>_<video_id>/` holding:

| file | what it is |
|---|---|
| `<stem>.txt` | the transcript, original Whisper output |
| `<stem>.md` | `archive-transcript/1`: front matter (title, url, video_id, fetched_at, sha256, chars, lines, extractor, format), a visible `> **Source:**` line, the transcript |
| `index.json` | the same metadata, machine-readable, plus the transcript sha256 |
| `url.txt` | the URL record (`key`, `canonical_url`, `acquired_via`, `status`) |
| `summary.md` | only with `--summary` |

It prints the batch line (`yt <slug> <url> <leaf>`), then `STEM=` and `FOLDER=`. Add the line to a
batch and the registry row as usual; `render_indices.py` then rewrites `url.txt` and the leaf views.

**Legacy mode.** `yt-transcribe.sh <url> [--output-dir DIR] [--category CAT]` still writes
`~/Transcriptions/<Category>/<safe_title>_<video_id>.txt` with the header below. It exists for old
callers; nothing new should land there.

```
URL: https://youtube.com/watch?v=...
Title: <Video Title>

[Full transcript content...]
```

Temporary media is deleted right after transcription.


## Operating Rules

Hard rules for agents:

- **MUST** use `{baseDir}/scripts/yt_archive.py` when a research root is known: that is the archive mode, the only one that produces a source
- **MUST** keep `{baseDir}/scripts/yt-transcribe.sh` for legacy output only
- **MUST** pass each requested video as a quoted positional argument to that script
- **MUST** prefer the full YouTube URL when the user provides one
- **MUST NOT** strip a provided YouTube URL down to a bare video ID before execution
- `youtube.com/live/<id>`, `youtube.com/shorts/<id>`, `youtu.be/<id>`, and bare 11-char IDs are acceptable; the script normalizes them internally
- **MUST** preserve `t=`, `start=`, and `end=` query params when using the user URL
- **MUST** use `timeout >= 7200` for normal full-video transcriptions unless the user explicitly wants a short clip
- **MUST NOT** use `timeout: 300` for a normal transcription request
- If the user gives a live URL, pass it through directly; do not invent a partial command from just the ID
- If the user gives multiple URLs, pass them all in one command when feasible
- On failure with `Unknown option`, treat it as an invocation contract bug first, not a Whisper failure
- On failure with `HTTP Error 403: Forbidden`, suspect a missing JavaScript runtime before anything
  else: check the `JS runtime:` line the script prints, and verify with `command -v node deno bun qjs`
- Treat `exitCode != 0` as failure, and also treat the run as failure if the output contains
  `Error:`, `Video unavailable`, `Unknown option`, or `Audio download failed`
- After a successful transcription, report the saved path first
- Do not claim success just because other transcript files already exist under the leaf's `sources/urls/`; a packed transcript is announced by its `FOLDER=` line
- **MUST NOT** create a second transcript tree: `~/Transcriptions` is legacy, never a destination
- Never launch a second run for the same URL while another run for it is still in progress
- If `--category` is omitted, infer it from the title (falling back to `Unsorted`); use
  `--category <Category>` only to force a different bucket
- Do not read the whole transcript back into the LLM by default; read only a short excerpt if needed
- After a successful transcription, if the user asks for a summary/report, follow the
  the `## Detailed AI Summary` section and save `summary.md` inside the packed source folder (or pass `--summary <path>` at pack time)
- When the user asks for a research plan / NotebookLM input, produce `research_plan.md` in the same
  source folder (legacy name: `<same-name>_AISEARCHPLAN.md`), for ANY input file, following the
  `### Research plan` subsection and staying under ~4,600 characters
- **MUST NOT** write secrets into any repo file; never commit tokens (keep them in a secrets store outside the repo)

## Runtime Notes

- The script logs the effective duration, model, CUDA device and the resolved JavaScript runtime before transcribing
- Long videos can legitimately take far longer than 6-10 minutes; tool timeouts must reflect video length
- Timestamped links like `...?t=276s` are clipped requests, not always full-video transcriptions

## Detailed AI Summary (`*_AISUMMARY.md`)

After a successful transcription, optionally produce a structured, implementation-oriented report of
the video and archive it next to the transcript. Purpose: turn a raw transcript into a navigable
knowledge artifact (macro-themes, sub-themes, fundamental concepts, quotes, actionable takeaways)
that is usable for frontier implementation work.

### Where to save

- **Archive mode (the default): inside the packed source folder.** Write `summary.md` beside the
  transcript, `<R>/data/<leaf>/sources/urls/<stem>/summary.md` (or pass `--summary <path>` at pack
  time). The summary is a file of that source, not a second tree.
- **Legacy mode only** (no research root known, an old caller): `~/Transcriptions/.agent/summaries/<Category>/`
  - `<Category>` MUST mirror the transcript's category subfolder.
  - If the transcript sits directly in `~/Transcriptions/` (no category), use `Unsorted`.
- Filename: same base name as the transcript with `_AISUMMARY.md` appended
  (`DHH_..._NYFGCESmikA.txt` -> `DHH_..._NYFGCESmikA_AISUMMARY.md`)
- Create the folder if missing (`mkdir -p`). Never mix metadata with the raw transcripts.

### How to build the summary

1. Read the transcript ENTIRELY before writing (it can be thousands of lines). Do not sample.
2. Extract, in this order: a titled header block with source metadata (URL, title, transcript path,
   duration, generator, date); a TL;DR of roughly 10-12 points; an ordered map of macro-themes (table:
   theme / focus / why it matters); for each macro-theme the sub-themes, fundamental concepts, verbatim
   key quotes and implications for frontier implementation; a glossary of recurring fundamental
   concepts; an actionable playbook; experiments/benchmarks mentioned; tensions/risks with
   counter-arguments; open questions; a short method note.
3. Keep it evidence-bound: every claim must trace back to the transcript and quotes must be verbatim.
   Mark paraphrases/translations explicitly. Never invent content.
4. Language: write the report in the user's language (default Italian), keeping technical terms in English.

### Rules

- Do NOT overwrite an existing `_AISUMMARY.md` without asking; if one exists, ask first or write a dated variant.
- Back up any file before overwriting it (`cp -a file file.bak-YYYYMMDD-HHMMSS`).
- The summary is a separate artifact: never modify or truncate the original `.txt` transcript.

### Research plan (`*_AISEARCHPLAN.md`)

For ANY input document - a transcription, or any other file the user provides - you can produce a
**research plan**: a compact, formal, deterministic brief meant to be pasted into NotebookLM (or a
similar deep-research tool) so it runs research across every theme of the input. It is NOT a summary,
and NOT a list of keywords: it is a set of instructions plus one context-anchored prompt per theme.

**Where to save**

- **Archive mode (the default):** the packed source folder,
  `<R>/data/<leaf>/sources/urls/<stem>/summary.md` or `research_plan.md` beside the transcript.
- **Legacy mode only** (no research root): `~/Transcriptions/.agent/summaries/<Category>/<same-name>_AISEARCHPLAN.md`
  (same folder and base name as the companion `_AISUMMARY.md` when one exists).
- Any other input file: `<input-dir>/.agent/<input-base-name>_AISEARCHPLAN.md` (create the `.agent`
  folder next to the source file if missing).
- Never modify or replace the source file.

**Size cap (NON NEGOTIABLE)**

- NotebookLM rejects long inputs: keep the plan within the length of the companion report's TL;DR +
  macro-theme map, i.e. at most ~4,600 characters / ~1,150 tokens. Target 3,600-4,400.
- Verify the real size before saving (`wc -c` / `.length`). If over, cut words, never themes.

**How to build it well (do NOT compress into a keyword list)**

1. Header (2-3 lines): the source of the input, the input file path, and the goal of the research.
2. A "Deterministic instructions" block: state the analyst role and require that EVERY theme be
   delivered as a card with the SAME fixed fields, in the SAME order. Default six fields: (1) framing,
   5-8 lines, what it is and why it matters; (2) state of the art with cited sources; (3) evidence
   for/against, separating facts from opinions; (4) contextual glossary, every technical term defined
   with an example; (5) risks, limits and unknowns; (6) three follow-up questions. Also state the
   language, the "no isolated technical terms" rule, the traceability rule, and the final deliverable
   shape (one document, themes in order, plus N priority research questions).
3. One section per theme, as `### Tn - <theme>` followed by ONE short paragraph made of a sentence of
   CONTEXT plus the research objective. Anchor every technical term inside the sentence and define it
   inline. NEVER emit bare term lists, entity lists or isolated keywords.
4. Keep it compact but complete: one short paragraph per theme, no repetition, no omissions.

**Rules**

- Deterministic and evidence-bound: the same structure for every theme, so results are comparable.
- Do not overwrite an existing `_AISEARCHPLAN.md` without asking; back up any file before overwriting it.
- The plan is a separate artifact: the source file stays untouched.
