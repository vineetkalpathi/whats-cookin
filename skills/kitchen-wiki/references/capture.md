# Capturing sources into `raw/`

How links, files, and pasted text become raw sources. Read this when you capture a source, or
when `capture.py` fails.

## Raw file conventions

- One source = one markdown file: `mise/raw/YYYY-MM-DD-<slug>.md` (capture date + slug).
- A binary original (PDF, image) sits next to it with the **same stem**:
  `2026-11-14-grandmas-recipes.pdf`. The `.md` embeds it with `![[...]]`.
- Images taken from a source go in `mise/raw/assets/`.
- The header records provenance:

  | field | meaning |
  |---|---|
  | `title`, `kind` | `kind`: `website`, `youtube`, `instagram`, `pdf`, `photo`, `note`, `book`, `family` |
  | `url` | canonical URL (used for duplicate detection) |
  | `author`, `site`, `published` | when known |
  | `captured` | date of capture |
  | `via` | how it was captured: `capture.py/json-ld`, `capture.py/yt-dlp`, `capture.py/file`, `web-fetch`, `paste`, `clipper` |
  | `file` | companion file name, for PDFs and images |

- **Raw files are immutable once written.** The one exception is the ingest step that fills a
  PDF or photo capture note's `## Contents` / `## Transcription` placeholders. That's
  completing the capture, not changing the source.

## Fallback order: never give up on a link

Run `python3 skills/kitchen-wiki/scripts/capture.py <url> --json`, then go by the exit code:

| exit | meaning | what to do |
|---|---|---|
| 0 | captured | ingest `path` |
| 2 | page has no structured recipe data (blogs, technique articles, news) | **web-fetch the page** and ask for the full article text: the recipe or technique content, with ingredient amounts and steps verbatim, and no ads or comments. Pipe that into `capture.py <url> --stdin --via web-fetch --title "<title>"` |
| 3 | `yt-dlp` missing | tell the user once (`brew install yt-dlp`). For now, web-fetch the YouTube page for the title and description, capture with `--stdin --kind youtube --via web-fetch`, and say the transcript is missing |
| 4 | fetch failed (403/429, timeout, login) | try a **web fetch** (it often gets through when the script can't). If that fails too, the page is probably paywalled or needs a login: **ask the user** to clip it with Web Clipper (see below) or paste the text |
| 5 | already captured | don't re-capture; ingest the existing `path` or check the wiki's `sources/` |
| 6 | Instagram / TikTok / Facebook | **ask the user to paste the caption** (and describe anything that's only in the video), then `capture.py <url> --stdin` |

Rules for `--stdin` captures:
- Pass the text **as the source gives it**: don't summarize, normalize, or fill gaps in this
  step. Normalizing happens at ingest.
- The user's own notes, family recipes, and "here's what I did" are captured with
  `capture.py - --stdin --kind note --title "..."` (or `--kind family`).

## By source type

**Recipe websites.** Most recipe sites embed a schema.org Recipe object in the page, and
`capture.py` turns it into ingredients, numbered steps, and times. The original structured data is
kept in a fenced JSON block at the bottom. If the capture carries the "structured data was
incomplete" warning, web-fetch the page at ingest to fill in what's missing.

**YouTube.** The capture holds the description, the chapters (with timestamped links), and a
transcript in 30-second paragraphs with timestamps. Auto-captions mishear food words ("cumin" →
"coming"), so fix them by context and flag anything you're unsure of at ingest. Cite timestamps
on technique pages: `[[source-slug]] @4:32`. If the description links a written recipe, capture
that too and treat it as the authoritative ingredient list.

**Instagram / TikTok.** Manual capture only (exit code 6). The caption usually has the recipe.
If the recipe is only in the video, the user's notes are the source.

**PDFs** (from Google Drive or anywhere): ask for the **local path** (e.g. from the Google Drive
for desktop folder). Private Drive share links need a login, so the script can't fetch them.
`capture.py <path>` copies the PDF into `raw/` and writes a capture note with an approximate
`pages` count.

At ingest:
1. **Survey.** Read a PDF over ~10 pages in ranges (max 20 pages per read). Start with the first
   pages for a table of contents.
2. **One recipe:** ingest it directly.
3. **Multiple recipes / cookbook:** fill the capture note's `## Contents` with the recipes found
   and their page numbers, show the list to the user, and ingest **only the recipes they pick**.
   Make one `sources/` page for the PDF, and have each recipe page cite it with page numbers
   (`[[source-slug]] p. 42`). Unpicked recipes stay listed in `## Contents` for later sessions.
4. **Scanned or handwritten pages:** write a faithful transcription into `## Transcription`,
   marking unsure readings `[?]`. Ask the user to check those before the recipe goes into the wiki.
   Later reads use the transcription rather than the scan.

**Photos** (recipe cards, cookbook pages): `capture.py <image-path>`, then transcribe it like a
scanned PDF.

## Obsidian Web Clipper (for paywalled and bot-blocked sites)

Use it when the script and web fetch both fail because the site needs the user's login (NYT
Cooking, America's Test Kitchen), or when the user wants to save pages while browsing.

Setup (the user does this once):
1. Install the Obsidian Web Clipper browser extension.
2. In its settings → **Templates → Import**, import both files from
   `skills/kitchen-wiki/assets/`:
   - `web-clipper-recipe.json`: triggers on pages with schema.org Recipe data
   - `web-clipper-article.json`: any other page (technique articles, guides)
3. Put **Kitchen recipe** above **Kitchen article** in the template list. The first matching
   trigger wins.
4. In the extension, set the vault to `mise`. Both templates save to `raw/`.

Clipped files have `via: clipper` and the same header fields as `capture.py` files, so ingest
treats them the same way. Two limitations to check at ingest:
- Instructions split into sections, or given as one text block, may come through incomplete.
- Times stay in ISO format (`PT1H5M`), and file names come from the page title, so they may
  not match the slug convention exactly. That's fine; don't rename raw files.
