#!/usr/bin/env python3
"""Append a meal to mise/meals.md (the history suggest.py reads).

Usage:
    python3 log_meal.py RECIPE_SLUG [--date YYYY-MM-DD] [--note TEXT] [--vault PATH] [--force]

Refuses unknown recipe slugs unless --force is given (so typos don't
silently break the LRU rotation).
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kitchen-wiki" / "scripts"))
from kitchen_vault import find_vault, load_vault, meals_path, norm_slug  # noqa: E402

HEADER = """---
type: meal-log
---
# Meal history

One line per meal: `- YYYY-MM-DD [[recipe-slug]] — optional note`.
Append-only; order doesn't matter. Read by the suggest-recipe skill.

"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recipe")
    ap.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--note", default="")
    ap.add_argument("--vault")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    root = find_vault(a.vault)
    slug = norm_slug(a.recipe.strip("[]"))
    v = load_vault(root)
    if v.get(slug, "recipe") is None and not a.force:
        close = [r.slug for r in v.of_type("recipe") if slug in r.slug or r.slug in slug]
        print(f"error: no recipe page '{slug}'." + (f" Did you mean: {', '.join(close)}?" if close else "")
              + " Use --force to log anyway.", file=sys.stderr)
        return 1

    path = meals_path(root)
    if not path.exists():
        path.write_text(HEADER, encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    line = f"- {a.date.isoformat()} [[{slug}]]" + (f" — {a.note}" if a.note else "")
    with path.open("a", encoding="utf-8") as f:
        if text and not text.endswith("\n"):
            f.write("\n")
        f.write(line + "\n")
    print(f"logged: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
