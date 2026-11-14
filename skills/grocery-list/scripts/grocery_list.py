#!/usr/bin/env python3
"""Aggregate ingredients from 1..n recipes into a grocery list.

Usage:
    python3 grocery_list.py RECIPE[:SCALE] [RECIPE[:SCALE] ...]
                            [--store SLUG] [--include-optional] [--out PATH]
                            [--vault PATH] [--json]

  RECIPE:SCALE   e.g. chana-masala:2 doubles that recipe.
  --store        store page slug (wiki/stores/); flags items the store
                 doesn't stock or that are specialty items it isn't known
                 to carry.
  --out          write the markdown list to this path (e.g. lists/2026-11-14.md
                 relative to the vault).

Quantities with the same dimension (volume, weight, or the same count unit)
are summed; incompatible units are listed side by side. Ingredients marked
`staple: true` go to a "check the pantry first" section.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kitchen-wiki" / "scripts"))
from kitchen_vault import (  # noqa: E402
    INGREDIENT_CATEGORIES, dimension, find_vault, fmt_amount, load_vault,
    parse_ingredient_line, to_base,
)


def parse_recipe_arg(s: str) -> tuple[str, Fraction]:
    slug, _, scale = s.partition(":")
    return slug.strip("[]"), Fraction(scale) if scale else Fraction(1)


def build(vault_root: Path, recipe_args: list[str], store_slug: str | None, include_optional: bool) -> dict:
    v = load_vault(vault_root)
    problems = []
    store = None
    if store_slug:
        store = v.get(store_slug, "store")
        if store is None:
            known = ", ".join(p.slug for p in v.of_type("store")) or "none"
            problems.append(f"unknown store '{store_slug}' (known: {known}); availability not checked")

    items: "OrderedDict[str, dict]" = OrderedDict()
    recipes_used = []
    for arg in recipe_args:
        slug, scale = parse_recipe_arg(arg)
        r = v.get(slug, "recipe")
        if r is None:
            problems.append(f"unknown recipe '{slug}' (skipped)")
            continue
        recipes_used.append({"recipe": slug, "title": r.title, "scale": str(scale)})
        for line in r.meta.get("ingredients") or []:
            use = parse_ingredient_line(line)
            if use is None:
                problems.append(f"{slug}: ingredient line without [[link]]: {line!r}")
                continue
            if use.optional and not include_optional:
                continue
            it = items.setdefault(use.slug, {"amounts": {}, "units": {}, "untracked": False,
                                             "recipes": [], "notes": [], "ranged": False})
            if slug not in it["recipes"]:
                it["recipes"].append(slug)
            if use.note:
                it["notes"].append(use.note)
            it["ranged"] |= use.ranged
            if use.qty is None:
                it["untracked"] = True  # "to taste", "a pinch of"...
                continue
            dim = dimension(use.unit)
            it["amounts"][dim] = it["amounts"].get(dim, Fraction(0)) + to_base(use.qty * scale, use.unit)
            it["units"].setdefault(dim, set()).add(use.unit)

    stocked = set(store.meta_links("stocked")) if store else set()
    not_stocked = set(store.meta_links("not_stocked")) if store else set()

    rows = []
    for slug, it in items.items():
        ing = v.get(slug, "ingredient")
        amounts = [fmt_amount(total, dim, it["units"][dim]) for dim, total in it["amounts"].items()]
        if it["untracked"]:
            amounts.append("to taste / as needed")
        flags = []
        if ing is None:
            flags.append("no ingredient page — availability unknown")
            category, staple, availability = "other", False, None
        else:
            category = ing.meta.get("category") or "other"
            staple = ing.meta.get("staple") is True
            availability = ing.meta.get("availability")
        if store is not None:
            if slug in not_stocked:
                flags.append(f"not stocked at {store.title}")
            elif availability == "specialty" and slug not in stocked:
                flags.append(f"specialty item — may not be at {store.title}")
        if availability == "seasonal":
            flags.append("seasonal")
        if it["ranged"]:
            flags.append("recipe gives a range; used the upper bound")
        rows.append({
            "ingredient": slug,
            "name": ing.title if ing else slug,
            "amount": " + ".join(amounts) if amounts else "",
            "category": category if category in INGREDIENT_CATEGORIES else "other",
            "staple": staple,
            "recipes": it["recipes"],
            "notes": sorted(set(it["notes"])),
            "flags": flags,
            "find_at": (ing.meta_links("find_at") if ing else []),
        })

    order = {c: i for i, c in enumerate(INGREDIENT_CATEGORIES)}
    rows.sort(key=lambda r: (r["staple"], order.get(r["category"], 99), r["name"].lower()))
    return {"recipes": recipes_used, "store": store.slug if store else None,
            "items": rows, "problems": problems}


def to_markdown(r: dict, today: str) -> str:
    out = ["---", "type: grocery-list", f"date: {today}"]
    out.append("recipes: [" + ", ".join(f'"[[{x["recipe"]}]]"' for x in r["recipes"]) + "]")
    if r["store"]:
        out.append(f'store: "[[{r["store"]}]]"')
    out += ["---", f"# Grocery list — {today}", ""]
    out.append("Recipes: " + ", ".join(
        f"[[{x['recipe']}]]" + (f" ×{x['scale']}" if x["scale"] != "1" else "") for x in r["recipes"]))

    def line(row):
        s = f"- [ ] **{row['name']}**"
        if row["amount"]:
            s += f" — {row['amount']}"
        extra = []
        if row["notes"]:
            extra.append("; ".join(row["notes"]))
        extra.append("for " + ", ".join(f"[[{x}]]" for x in row["recipes"]))
        s += f" ({' · '.join(extra)})"
        if row["flags"]:
            s += " ⚠️ " + "; ".join(row["flags"])
            if row["find_at"]:
                s += " — try " + ", ".join(f"[[{x}]]" for x in row["find_at"])
        return s

    current = None
    for row in [x for x in r["items"] if not x["staple"]]:
        if row["category"] != current:
            current = row["category"]
            out += ["", f"## {current.replace('-', ' / ').title()}"]
        out.append(line(row))
    staples = [x for x in r["items"] if x["staple"]]
    if staples:
        out += ["", "## Check the pantry first (staples)"]
        out += [line(x) for x in staples]
    flagged = [x for x in r["items"] if x["flags"]]
    if flagged:
        out += ["", "## Availability flags"]
        out += [f"- {x['name']}: {'; '.join(x['flags'])}" for x in flagged]
    if r["problems"]:
        out += ["", "## Problems"] + [f"- {p}" for p in r["problems"]]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recipes", nargs="+")
    ap.add_argument("--store")
    ap.add_argument("--include-optional", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--vault")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = find_vault(a.vault)
    r = build(root, a.recipes, a.store, a.include_optional)
    if a.json:
        print(json.dumps(r, indent=2))
        return 0 if r["recipes"] else 1
    md = to_markdown(r, dt.date.today().isoformat())
    if a.out:
        out = Path(a.out)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"wrote {out}")
    print(md)
    return 0 if r["recipes"] else 1


if __name__ == "__main__":
    sys.exit(main())
