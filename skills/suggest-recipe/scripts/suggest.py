#!/usr/bin/env python3
"""Deterministic least-recently-eaten recipe suggestion.

Usage:
    python3 suggest.py [--date YYYY-MM-DD] [--cooldown-days N] [--count N]
                       [--exclude-cuisine SLUG ...] [--exclude-recipe SLUG ...]
                       [--vault PATH] [--json]

Algorithm (same vault + same --date => same answer):
  1. Eligible recipes: type: recipe, not `rotation: false`, not eaten in the
     last --cooldown-days (default 14), not excluded.
  2. For every cuisine, last_eaten = most recent meals.md entry of any recipe
     tagged with that cuisine (never eaten = oldest possible).
  3. Pick the cuisine with the oldest last_eaten that still has an eligible
     recipe.
  4. Inside it, pick the eligible recipe with the oldest last_eaten.
  Ties are broken by sha256("<ISO year>-W<week>:<slug>"), so ties rotate
  week to week but are stable within a week.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kitchen-wiki" / "scripts"))
from kitchen_vault import find_vault, load_meals, load_vault  # noqa: E402

NEVER = "0000-00-00"


def tiebreak(week: str, slug: str) -> str:
    return hashlib.sha256(f"{week}:{slug}".encode()).hexdigest()


def servings_of(meta: dict) -> tuple[int | float | None, str]:
    """(servings, yield_unit) as written on the recipe; servings is None if missing or invalid."""
    n = meta.get("servings")
    if isinstance(n, bool) or not isinstance(n, (int, float)) or n <= 0:
        n = None
    elif isinstance(n, float) and n.is_integer():
        n = int(n)
    unit = meta.get("yield_unit")
    unit = unit.strip() if isinstance(unit, str) and unit.strip() else "servings"
    return n, unit


def servings_text(n: int | float | None, unit: str) -> str:
    if n is None:
        return "servings: not set"
    if unit == "servings":
        return f"serves {n} as written"
    return f"makes {n} {unit} as written"


def suggest(vault_root: Path, today: dt.date, cooldown: int, count: int,
            exclude_cuisines: set[str], exclude_recipes: set[str]) -> dict:
    v = load_vault(vault_root)
    iso = today.isocalendar()
    week = f"{iso[0]}-W{iso[1]:02d}"
    cutoff = (today - dt.timedelta(days=cooldown)).isoformat()

    recipes = {r.slug: r for r in v.of_type("recipe") if r.meta.get("rotation") is not False}
    last: dict[str, str] = {}
    unknown = set()
    for date, slug, _ in load_meals(vault_root):
        if date > today.isoformat():
            continue
        if slug not in v.pages:
            unknown.add(slug)
        last[slug] = max(last.get(slug, NEVER), date)

    cuisine_recipes: dict[str, list[str]] = {}
    for slug, r in recipes.items():
        for c in r.meta_links("cuisine"):
            cuisine_recipes.setdefault(c, []).append(slug)

    def eligible(slug: str) -> bool:
        return slug not in exclude_recipes and last.get(slug, NEVER) <= cutoff

    cuisine_last = {c: max((last.get(s, NEVER) for s in rs), default=NEVER)
                    for c, rs in cuisine_recipes.items()}
    ranked_cuisines = sorted(
        (c for c in cuisine_recipes if c not in exclude_cuisines),
        key=lambda c: (cuisine_last[c], tiebreak(week, c)))

    picks = []
    used = set()
    for c in ranked_cuisines:
        cands = sorted((s for s in cuisine_recipes[c] if eligible(s) and s not in used),
                       key=lambda s: (last.get(s, NEVER), tiebreak(week, s)))
        if not cands:
            continue
        s = cands[0]
        used.add(s)
        servings, yield_unit = servings_of(recipes[s].meta)
        picks.append({
            "recipe": s,
            "title": recipes[s].title,
            "path": str(recipes[s].path.relative_to(vault_root)),
            "servings": servings,
            "yield_unit": yield_unit,
            "cuisine": c,
            "cuisine_last_eaten": None if cuisine_last[c] == NEVER else cuisine_last[c],
            "recipe_last_eaten": last.get(s),
            "other_candidates_in_cuisine": cands[1:],
        })
        if len(picks) >= count:
            break

    return {
        "date": today.isoformat(),
        "week": week,
        "cooldown_days": cooldown,
        "suggestions": picks,
        "cuisine_ranking": [{"cuisine": c, "last_eaten": None if cuisine_last[c] == NEVER else cuisine_last[c]}
                            for c in ranked_cuisines],
        "meals_referencing_unknown_recipes": sorted(unknown),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault")
    ap.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--cooldown-days", type=int, default=14)
    ap.add_argument("--count", type=int, default=1, help="number of suggestions (each from a different cuisine)")
    ap.add_argument("--exclude-cuisine", nargs="*", default=[])
    ap.add_argument("--exclude-recipe", nargs="*", default=[])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    r = suggest(find_vault(a.vault), a.date, a.cooldown_days, a.count,
                set(a.exclude_cuisine), set(a.exclude_recipe))
    if a.json:
        print(json.dumps(r, indent=2))
        return 0 if r["suggestions"] else 2

    print(f"Suggestions for {r['date']} ({r['week']}, cooldown {r['cooldown_days']} days)\n")
    if not r["suggestions"]:
        print("No eligible recipes. Add recipes, shorten --cooldown-days, or drop exclusions.")
        return 2
    for i, s in enumerate(r["suggestions"], 1):
        print(f"{i}. [[{s['recipe']}]] {s['title']}  ({s['path']})")
        print(f"   {servings_text(s['servings'], s['yield_unit'])}")
        print(f"   cuisine [[{s['cuisine']}]] last eaten: {s['cuisine_last_eaten'] or 'never'}; "
              f"this recipe last eaten: {s['recipe_last_eaten'] or 'never'}")
        if s["other_candidates_in_cuisine"]:
            print(f"   next in this cuisine: {', '.join(s['other_candidates_in_cuisine'][:3])}")
    print("\nCuisine ranking (oldest first): "
          + ", ".join(f"{c['cuisine']} ({c['last_eaten'] or 'never'})" for c in r["cuisine_ranking"]))
    if r["meals_referencing_unknown_recipes"]:
        print("\nmeals.md links to recipes with no wiki page: "
              + ", ".join(r["meals_referencing_unknown_recipes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
