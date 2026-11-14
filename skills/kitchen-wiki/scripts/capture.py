#!/usr/bin/env python3
"""Capture a source (URL, local file, or pasted text) into mise/raw/ as markdown.

Usage:
    python3 capture.py URL_OR_PATH [--title T] [--slug S] [--kind K] [--date YYYY-MM-DD]
                       [--stdin] [--via LABEL] [--vault PATH] [--force] [--json]

Sources:
  recipe website URL   fetches the page, extracts the schema.org Recipe JSON-LD
  YouTube URL          transcript + description + chapters (requires yt-dlp)
  local file           copies a PDF/image/text file into raw/ and writes a .md capture note
  --stdin              body text comes from stdin (pasted caption, agent web-fetch output,
                       your own notes). URL_OR_PATH is then the URL, or "-" if there is none.

Output: raw/YYYY-MM-DD-<slug>.md (+ a companion file with the same stem for local files).
Raw files are immutable: an existing file is never overwritten unless --force is passed.

Exit codes:
  0 captured           1 usage error
  2 no structured recipe found on the page; fall back to web fetch + --stdin
  3 missing dependency (yt-dlp)
  4 fetch failed (HTTP error, blocked, timeout); fall back to web fetch or ask the user
  5 already captured (path printed); ingest the existing file instead
  6 manual capture needed (Instagram/TikTok/Facebook); rerun with --stdin and pasted text
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitchen_vault import find_vault, split_frontmatter, parse_frontmatter  # noqa: E402

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) recipe-capture/0.1"
MANUAL_HOSTS = ("instagram.com", "tiktok.com", "facebook.com", "fb.watch", "threads.net")
YOUTUBE_RE = re.compile(r"^https?://(www\.|m\.)?(youtube\.com/(watch|shorts/|live/)|youtu\.be/)")
TEXT_EXT = {".md", ".txt", ".markdown"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}


class CaptureError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r"['’]", "", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode())
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:max_len].rstrip("-") or "untitled"


def yaml_str(value) -> str:
    s = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{s}"'


def iso_minutes(duration) -> int | None:
    """ISO-8601 duration (PT1H30M, P0DT0H20M) -> minutes."""
    if not duration or not isinstance(duration, str):
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?", duration.strip())
    if not m:
        return None
    d, h, mi, s = (float(x) if x else 0 for x in m.groups())
    total = int(round(d * 1440 + h * 60 + mi + s / 60))
    return total or None


def text_of(value) -> str:
    """Flatten a JSON-LD value (str / dict with name|text / list) into plain text."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(t for t in (text_of(v) for v in value) if t)
    if isinstance(value, dict):
        return text_of(value.get("name") or value.get("text") or "")
    return clean(str(value))


def clean(s: str) -> str:
    s = html.unescape(html.unescape(s))
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def existing_capture(raw: Path, url: str | None) -> Path | None:
    if not url:
        return None
    norm = url.split("#")[0].rstrip("/")
    for p in raw.glob("*.md"):
        try:
            fm, _ = split_frontmatter(p.read_text(encoding="utf-8"))
            meta = parse_frontmatter(fm) if fm else {}
        except Exception:
            continue
        if str(meta.get("url") or "").split("#")[0].rstrip("/") == norm:
            return p
    return None


def write_capture(raw: Path, date: str, slug: str, meta: dict, body: str, force: bool) -> Path:
    path = raw / f"{date}-{slug}.md"
    if path.exists() and not force:
        raise CaptureError(5, f"already exists: {path} (raw files are immutable; pass --force to overwrite)")
    lines = ["---"]
    for k, v in meta.items():
        if v in (None, "", []):
            continue
        if isinstance(v, list):
            lines.append(f"{k}: [" + ", ".join(yaml_str(x) for x in v) + "]")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {yaml_str(v)}")
    lines.append("---")
    path.write_text("\n".join(lines) + "\n" + body.rstrip() + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# websites (schema.org Recipe JSON-LD)
# --------------------------------------------------------------------------

class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.jsonld: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_ld = self._in_title = False
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower().strip() == "application/ld+json":
            self._in_ld, self._buf = True, ""
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta.setdefault(key.lower(), a["content"])

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self.jsonld.append(self._buf)
            self._in_ld = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_ld:
            self._buf += data
        elif self._in_title:
            self.title += data


def _walk_ld(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk_ld(n)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk_ld(node[key])


def _is_recipe(node: dict) -> bool:
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.split("/")[-1] == "Recipe" for x in types)


def find_recipe(blocks: list[str]) -> dict | None:
    for raw in blocks:
        try:
            data = json.loads(raw.strip().rstrip(";"))
        except json.JSONDecodeError:
            continue
        for node in _walk_ld(data):
            if _is_recipe(node):
                return node
    return None


def image_url(value) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    return str(value) if value else None


def instructions_md(value) -> list[str]:
    """recipeInstructions: str | [str] | [HowToStep] | [HowToSection{itemListElement}]."""
    out: list[str] = []
    n = 0

    def step(text):
        nonlocal n
        text = clean(text)
        if text:
            n += 1
            out.append(f"{n}. {text}")

    if isinstance(value, str):
        parts = [p for p in re.split(r"\n+|(?<=\.)\s{2,}", clean_keep_lines(value)) if p.strip()]
        for p in parts:
            step(p)
        return out
    for item in value or []:
        if isinstance(item, str):
            step(item)
        elif isinstance(item, dict):
            t = item.get("@type")
            if t == "HowToSection" or "itemListElement" in item:
                if item.get("name"):
                    out.append(f"\n**{clean(item['name'])}**\n")
                for sub in item.get("itemListElement") or []:
                    step((sub.get("text") or sub.get("name") or "") if isinstance(sub, dict) else sub)
            else:
                step(item.get("text") or item.get("name") or "")
    return out


def clean_keep_lines(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s, flags=re.I)
    return re.sub(r"<[^>]+>", "", s)


def fetch(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8",
                                               "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            return r.geturl(), r.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        hint = " (site likely blocks scripts or needs a login)" if e.code in (401, 402, 403, 429) else ""
        raise CaptureError(4, f"HTTP {e.code} fetching {url}{hint}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise CaptureError(4, f"could not fetch {url}: {getattr(e, 'reason', e)}")


def capture_website(url: str, args) -> tuple[dict, str, str]:
    final_url, page = fetch(url)
    p = _PageParser()
    p.feed(page)
    recipe = find_recipe(p.jsonld)
    if recipe is None:
        title = clean(p.meta.get("og:title") or p.title) or url
        raise CaptureError(2, f"no schema.org Recipe data on '{title}'. Fall back to a web fetch of the "
                              "page and rerun with --stdin (and --via web-fetch).")
    name = clean(recipe.get("name") or p.meta.get("og:title") or p.title)
    ingredients = [clean(i) for i in (recipe.get("recipeIngredient") or recipe.get("ingredients") or []) if clean(str(i))]
    steps = instructions_md(recipe.get("recipeInstructions"))
    yld = recipe.get("recipeYield")
    yld = text_of(yld[0] if isinstance(yld, list) and yld else yld)
    meta = {
        "title": args.title or name,
        "kind": "website",
        "url": final_url,
        "site": p.meta.get("og:site_name") or text_of(recipe.get("publisher")),
        "author": text_of(recipe.get("author")),
        "published": str(recipe.get("datePublished") or "")[:10],
        "captured": args.date,
        "via": "capture.py/json-ld",
        "yield": yld,
        "prep_time": iso_minutes(recipe.get("prepTime")),
        "cook_time": iso_minutes(recipe.get("cookTime")),
        "total_time": iso_minutes(recipe.get("totalTime")),
        "recipe_cuisine": text_of(recipe.get("recipeCuisine")),
        "recipe_category": text_of(recipe.get("recipeCategory")),
        "image": image_url(recipe.get("image")),
    }
    body = [f"# {name}", ""]
    if recipe.get("description"):
        body += [clean(recipe["description"]), ""]
    body += ["## Ingredients", ""] + [f"- {i}" for i in ingredients]
    body += ["", "## Instructions", ""] + steps
    if not ingredients or not steps:
        body += ["", "> [!warning] Structured data was incomplete (missing ingredients or steps). "
                     "Check the page and add what's missing to the wiki at ingest time."]
    body += ["", "## Structured data (original)", "", "```json",
             json.dumps(recipe, indent=2, ensure_ascii=False), "```"]
    return meta, "\n".join(body), slugify(args.slug or name)


# --------------------------------------------------------------------------
# YouTube (yt-dlp)
# --------------------------------------------------------------------------

def _ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_vtt(text: str, para_seconds: int = 30) -> list[str]:
    cue_re = re.compile(r"^(\d+:)?(\d{2}):(\d{2})\.\d{3}\s+-->")
    paras, cur, cur_start, last = [], [], None, None
    start = 0.0
    for line in text.splitlines():
        m = cue_re.match(line)
        if m:
            h = int(m.group(1)[:-1]) if m.group(1) else 0
            start = h * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")) or line == last:
            continue
        last = line
        if cur_start is None:
            cur_start = start
        if start - cur_start >= para_seconds and cur:
            paras.append(f"**[{_ts(cur_start)}]** " + " ".join(cur))
            cur, cur_start = [], start
        cur.append(html.unescape(line))
    if cur:
        paras.append(f"**[{_ts(cur_start or 0)}]** " + " ".join(cur))
    return paras


def capture_youtube(url: str, args) -> tuple[dict, str, str]:
    if shutil.which("yt-dlp") is None:
        raise CaptureError(3, "yt-dlp is not installed (install: `brew install yt-dlp` or `pipx install yt-dlp`). "
                              "Fallback: paste the description/transcript and rerun with --stdin --kind youtube.")
    with tempfile.TemporaryDirectory(prefix="capture-yt-") as tmp:
        cmd = ["yt-dlp", "--skip-download", "--write-info-json", "--write-subs", "--write-auto-subs",
               "--sub-langs", "en.*,en", "--sub-format", "vtt", "--no-playlist",
               "-o", str(Path(tmp) / "%(id)s.%(ext)s"), url]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        infos = list(Path(tmp).glob("*.info.json"))
        if not infos:
            raise CaptureError(4, f"yt-dlp failed: {(r.stderr or r.stdout).strip()[-500:]}")
        info = json.loads(infos[0].read_text(encoding="utf-8"))
        vtts = sorted(Path(tmp).glob("*.vtt"), key=lambda p: ("orig" in p.name, len(p.name)))
        transcript = parse_vtt(vtts[0].read_text(encoding="utf-8")) if vtts else []
        sub_kind = ("manual" if vtts and info.get("subtitles") and any(
            k.startswith("en") for k in info["subtitles"]) else "auto") if vtts else None

    title = info.get("title") or url
    vid_url = info.get("webpage_url") or url
    desc = info.get("description") or ""
    links = sorted(set(re.findall(r"https?://[^\s)>\]]+", desc)))
    meta = {
        "title": args.title or title,
        "kind": "youtube",
        "url": vid_url,
        "author": info.get("uploader") or info.get("channel"),
        "published": (f"{info['upload_date'][:4]}-{info['upload_date'][4:6]}-{info['upload_date'][6:]}"
                      if info.get("upload_date") else None),
        "captured": args.date,
        "via": "capture.py/yt-dlp",
        "duration_min": round(info["duration"] / 60) if info.get("duration") else None,
        "transcript": sub_kind or "none",
    }
    body = [f"# {title}", "", f"<{vid_url}>", "", "## Description", "", desc.strip() or "*(none)*"]
    if info.get("chapters"):
        body += ["", "## Chapters", ""] + [
            f"- [{_ts(c['start_time'])}]({vid_url}&t={int(c['start_time'])}s) {c.get('title', '')}"
            if "?" in vid_url else f"- [{_ts(c['start_time'])}]({vid_url}?t={int(c['start_time'])}s) {c.get('title', '')}"
            for c in info["chapters"]]
    body += ["", "## Transcript", ""]
    body += transcript or ["*(no English transcript available. Add notes from watching, or screenshots in raw/assets/)*"]
    if links:
        body += ["", "## Links in description", ""] + [f"- {u}" for u in links]
    return meta, "\n".join(body), slugify(args.slug or title)


# --------------------------------------------------------------------------
# local files and pasted text
# --------------------------------------------------------------------------

def capture_file(path: Path, args, raw: Path) -> tuple[dict, str, str, Path | None]:
    if not path.is_file():
        raise CaptureError(1, f"no such file: {path}")
    ext = path.suffix.lower()
    slug = slugify(args.slug or args.title or path.stem)
    title = args.title or path.stem.replace("_", " ").replace("-", " ").strip()
    meta = {"title": title, "kind": args.kind or ("pdf" if ext == ".pdf" else "photo" if ext in IMAGE_EXT else "note"),
            "captured": args.date, "via": "capture.py/file", "original_name": path.name}
    if ext in TEXT_EXT:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = split_frontmatter(text) if text.startswith("---") else (None, text)
        return meta, body.strip(), slug, None
    companion = raw / f"{args.date}-{slug}{ext}"
    if companion.exists() and not args.force:
        raise CaptureError(5, f"already exists: {companion}")
    shutil.copy2(path, companion)
    meta["file"] = companion.name
    if ext == ".pdf":
        size_kb = companion.stat().st_size // 1024
        approx_pages = len(re.findall(rb"/Type\s*/Page[^s]", companion.read_bytes()))
        meta["pages"] = approx_pages or None
        body = [f"# {title}", "", f"![[{companion.name}]]", "",
                f"PDF, about {approx_pages or '?'} pages, {size_kb} KB.",
                "", "## Contents", "", "*(filled in at ingest: recipes found and their page numbers)*",
                "", "## Transcription", "",
                "*(only for scanned or handwritten pages: written at ingest, with [?] marking unsure readings)*"]
    else:
        body = [f"# {title}", "", f"![[{companion.name}]]", "", "## Transcription", "",
                "*(written at ingest, with [?] marking unsure readings)*"]
    return meta, "\n".join(body), slug, companion


def capture_stdin(source: str | None, args) -> tuple[dict, str, str]:
    text = sys.stdin.read().strip()
    if not text:
        raise CaptureError(1, "--stdin given but no text on stdin")
    first = next((l.strip("# ").strip() for l in text.splitlines() if l.strip()), "untitled")
    title = args.title or first[:80]
    kind = args.kind or ("instagram" if source and "instagram.com" in source else
                         "youtube" if source and YOUTUBE_RE.match(source) else
                         "website" if source else "note")
    meta = {"title": title, "kind": kind, "url": source, "captured": args.date, "via": args.via or "paste"}
    return meta, text, slugify(args.slug or title)


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="URL, local file path, or '-' (with --stdin and no URL)")
    ap.add_argument("--title")
    ap.add_argument("--slug")
    ap.add_argument("--kind", help="website|pdf|youtube|instagram|note|photo|book|family (default: inferred)")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--stdin", action="store_true", help="read the body text from stdin")
    ap.add_argument("--via", help="provenance label for --stdin captures, e.g. web-fetch, paste, clipper")
    ap.add_argument("--vault")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    raw = find_vault(args.vault) / "raw"
    raw.mkdir(exist_ok=True)
    src = args.source.strip()
    is_url = bool(re.match(r"^https?://", src))
    companion = None
    try:
        if is_url and not args.force and (dup := existing_capture(raw, src)):
            raise CaptureError(5, f"already captured: {dup}")
        if args.stdin:
            meta, body, slug = capture_stdin(src if is_url else None, args)
        elif is_url and any(h in src.split("/")[2] for h in MANUAL_HOSTS):
            raise CaptureError(6, "this site can't be captured automatically. Paste the caption or "
                                  "your notes and rerun: capture.py URL --stdin")
        elif is_url and YOUTUBE_RE.match(src):
            meta, body, slug = capture_youtube(src, args)
        elif is_url:
            meta, body, slug = capture_website(src, args)
        else:
            meta, body, slug, companion = capture_file(Path(src).expanduser(), args, raw)
        path = write_capture(raw, args.date, slug, meta, body, args.force)
    except CaptureError as e:
        if args.json:
            print(json.dumps({"ok": False, "code": e.code, "error": str(e)}))
        else:
            print(f"error: {e}", file=sys.stderr)
        return e.code

    result = {"ok": True, "path": str(path.relative_to(raw.parent)), "kind": meta.get("kind"),
              "title": meta.get("title"), "companion": companion.name if companion else None}
    if meta.get("kind") == "youtube":
        result["description_links"] = re.findall(r"^- (https?://\S+)$", body, re.M)
    print(json.dumps(result, indent=2) if args.json else f"captured: {result['path']}"
          + (f" (+ {result['companion']})" if companion else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
