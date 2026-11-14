#!/usr/bin/env python3
"""Health-check the kitchen wiki.

Usage:
    python3 lint.py [--vault PATH] [--json]
    python3 lint.py --hash PATH     # print sha256 of a file (for raw_sha256)

Errors (exit code 1): unparseable frontmatter, missing required fields,
type/folder mismatch, duplicate slugs, ingredient lines without a link,
frontmatter edge links to pages that don't exist, recipe `servings`
that isn't a positive number, empty or non-string `yield_unit`, raw files whose sha256
no longer matches the source page's `raw_sha256`.
Warnings: missing reciprocal edges (incl. sources <-> informs), stale
backlinks, body links missing from frontmatter edges, unresolved `[?]`
transcription marks in raw files, missing or unstamped raw files, other
links to pages that don't exist yet, orphan pages, pages missing from
index.md, unknown ingredient categories.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitchen_vault import (  # noqa: E402
    FOLDER_TYPES, INGREDIENT_CATEGORIES, REQUIRED_FIELDS, find_vault,
    links_in, load_vault, parse_ingredient_line, parse_servings, sha256_file,
)

# (source type, source key, target type, target keys that must link back)
RECIPROCAL = [
    ("recipe", "ingredients", "ingredient", ("used_in",)),
    ("recipe", "equipment", "equipment", ("used_in",)),
    ("recipe", "techniques", "technique", ("used_in",)),
    ("recipe", "cuisine", "cuisine", ("recipes",)),
    ("ingredient", "used_in", "recipe", ("ingredients",)),
    ("equipment", "used_in", "recipe", ("equipment",)),
    ("technique", "used_in", "recipe", ("techniques",)),
    ("cuisine", "recipes", "recipe", ("cuisine",)),
    ("equipment", "techniques", "technique", ("equipment",)),
    ("technique", "equipment", "equipment", ("techniques",)),
    ("ingredient", "cuisines", "cuisine", ("common_ingredients", "spice_profile")),
    ("cuisine", "common_ingredients", "ingredient", ("cuisines",)),
    ("cuisine", "spice_profile", "ingredient", ("cuisines",)),
    # "*" = any page type
    ("*", "sources", "source", ("informs",)),
    ("source", "informs", "*", ("sources",)),
]

# frontmatter keys that are graph edges: a dangling link here is an error
EDGE_KEYS = (
    "ingredients", "equipment", "techniques", "cuisine", "used_in", "recipes",
    "cuisines", "common_ingredients", "spice_profile", "stocked", "not_stocked",
    "find_at", "sources", "informs", "parent", "related",
)

# page type -> {linked page type: frontmatter key that must hold body links to it}
BODY_EDGES = {
    "recipe": {"ingredient": "ingredients", "equipment": "equipment",
               "technique": "techniques", "cuisine": "cuisine"},
    "technique": {"equipment": "equipment"},
}

UNSURE_MARK = "[?]"

SPECIAL_PAGES = {"index", "log", "overview"}


def lint(vault_root: Path) -> dict:
    v = load_vault(vault_root)
    errors, warnings = [], []

    def rel(p):
        return str(p.path.relative_to(v.root))

    for slug, paths in v.duplicates.items():
        errors.append(f"duplicate slug '{slug}' (Obsidian links become ambiguous): "
                      + ", ".join(str(p.relative_to(v.root)) for p in paths))

    for p in v.pages.values():
        if p.error:
            errors.append(f"{rel(p)}: frontmatter: {p.error}")
            continue
        if p.slug in SPECIAL_PAGES and not p.folder:
            continue
        expected = FOLDER_TYPES.get(p.folder)
        if expected and p.meta.get("type") != expected:
            errors.append(f"{rel(p)}: type should be '{expected}' (got {p.meta.get('type')!r})")
        for f in REQUIRED_FIELDS.get(p.type or "", []):
            if p.meta.get(f) in (None, "", []):
                errors.append(f"{rel(p)}: missing required field '{f}'")
        if p.type == "recipe":
            sv = p.meta.get("servings")
            if sv not in (None, "", []) and parse_servings(sv) is None:
                errors.append(f"{rel(p)}: servings must be a positive number (got {sv!r})")
            if "yield_unit" in p.meta:
                yu = p.meta.get("yield_unit")
                if not isinstance(yu, str) or not yu.strip():
                    errors.append(f"{rel(p)}: yield_unit must be a non-empty string "
                                  f"(got {yu!r}), e.g. cookies, loaves, cups")
            for line in p.meta.get("ingredients") or []:
                if parse_ingredient_line(line) is None:
                    errors.append(f"{rel(p)}: ingredient line has no [[link]]: {line!r}")
        if p.type == "ingredient":
            cat = p.meta.get("category")
            if cat and cat not in INGREDIENT_CATEGORIES:
                warnings.append(f"{rel(p)}: unknown category '{cat}' "
                                f"(known: {', '.join(INGREDIENT_CATEGORIES)})")

    def pages_of(t):
        if t == "*":
            return sorted((p for p in v.pages.values() if not p.error), key=lambda p: p.slug)
        return v.of_type(t)

    # reciprocal edges
    missing_recip = []
    for src_t, src_k, dst_t, dst_ks in RECIPROCAL:
        for src in pages_of(src_t):
            for target in dict.fromkeys(src.meta_links(src_k)):
                dst = v.get(target)
                if dst is None or (dst_t != "*" and dst.type != dst_t):
                    continue
                if src.slug not in dst.meta_links(*dst_ks):
                    missing_recip.append(
                        f"{src.slug}.{src_k} -> [[{dst.slug}]] but {dst.slug}.{'/'.join(dst_ks)} "
                        f"does not link [[{src.slug}]]")

    # body links that never made it into the frontmatter edges (missed fanout)
    body_missing = []
    for p in sorted(v.pages.values(), key=lambda p: p.slug):
        wanted = BODY_EDGES.get(p.type or "")
        if not wanted or p.error:
            continue
        for target in dict.fromkeys(links_in(p.body)):
            dst = v.get(target)
            if dst is None or dst.slug == p.slug or dst.type not in wanted:
                continue
            key = wanted[dst.type]
            if dst.slug not in p.meta_links(key):
                body_missing.append(f"{p.slug}: body links [[{dst.slug}]] ({dst.type}) "
                                    f"but frontmatter {key} doesn't")

    # broken links and inbound counts. Dangling edge-key links are errors;
    # anything else (body, substitutes, other keys) is a page-to-create hint.
    inbound = {s: 0 for s in v.pages}
    broken: dict[str, set[str]] = {}
    for p in v.pages.values():
        for target in p.all_links():
            if target in v.pages and target != p.slug:
                inbound[target] += 1
        for k in EDGE_KEYS:
            for target in dict.fromkeys(links_in(p.meta.get(k))):
                if target not in v.pages:
                    errors.append(f"{rel(p)}: {k} links [[{target}]], which doesn't exist")
        other = set(links_in(p.body))
        for k, val in p.meta.items():
            if k not in EDGE_KEYS:
                other.update(links_in(val))
        for target in other:
            if target not in v.pages:
                broken.setdefault(target, set()).add(p.slug)

    # raw files behind source pages: existence, immutability stamp, [?] marks
    unresolved = []
    for src in v.of_type("source"):
        raw = src.meta.get("raw")
        if not raw or not isinstance(raw, str):
            continue
        raw_path = v.root / raw.strip()
        if not raw_path.is_file():
            warnings.append(f"{rel(src)}: raw file '{raw}' doesn't exist")
            continue
        stamp = src.meta.get("raw_sha256")
        if stamp in (None, "", []):
            warnings.append(f"{rel(src)}: raw file not stamped (add raw_sha256 from "
                            f"`lint.py --hash {raw}`)")
        elif str(stamp).strip().lower() != sha256_file(raw_path):
            errors.append(f"{rel(src)}: raw file changed since ingest "
                          f"('{raw}' no longer matches raw_sha256)")
        try:
            n = raw_path.read_text(encoding="utf-8", errors="replace").count(UNSURE_MARK)
        except OSError:
            n = 0
        if n:
            citing = [r.slug for r in v.of_type("recipe") if src.slug in r.meta_links("sources")]
            unresolved.append(f"{src.slug}: {n} unresolved [?] in '{raw}'; cited by: "
                              + (", ".join(f"[[{c}]]" for c in citing) or "(no recipes)"))

    orphans = sorted(s for s, n in inbound.items() if n == 0 and s not in SPECIAL_PAGES)

    index = v.get("index")
    indexed = index.all_links() if index else set()
    not_indexed = sorted(s for s, p in v.pages.items()
                         if s not in SPECIAL_PAGES and s not in indexed)

    return {
        "vault": str(v.root),
        "pages": len(v.pages),
        "errors": errors,
        "warnings": warnings,
        "missing_reciprocal_edges": missing_recip,
        "body_links_missing_from_edges": body_missing,
        "unresolved_transcriptions": unresolved,
        "missing_pages": {k: sorted(s) for k, s in sorted(broken.items())},
        "orphans": orphans,
        "not_in_index": not_indexed,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--hash", metavar="PATH",
                    help="print the sha256 of PATH (relative to the vault root, or absolute) and exit")
    args = ap.parse_args()
    if args.hash:
        path = Path(args.hash).expanduser()
        if not path.is_absolute():
            in_vault = find_vault(args.vault) / path
            path = in_vault if in_vault.is_file() or not path.is_file() else path
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2
        print(sha256_file(path))
        return 0
    r = lint(find_vault(args.vault))
    if args.json:
        print(json.dumps(r, indent=2))
        return 1 if r["errors"] else 0

    print(f"Linted {r['pages']} pages in {r['vault']}\n")
    sections = [
        ("ERRORS", r["errors"]),
        ("Warnings", r["warnings"]),
        ("Missing reciprocal edges", r["missing_reciprocal_edges"]),
        ("Body links missing from frontmatter edges", r["body_links_missing_from_edges"]),
        ("Unresolved transcription marks [?]", r["unresolved_transcriptions"]),
        ("Linked but missing pages (candidates to create)",
         [f"[[{k}]] <- {', '.join(v)}" for k, v in r["missing_pages"].items()]),
        ("Orphans (no inbound links)", r["orphans"]),
        ("Not listed in index.md", r["not_in_index"]),
    ]
    for title, items in sections:
        print(f"## {title}: {len(items)}")
        for it in items:
            print(f"  - {it}")
        print()
    return 1 if r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
