#!/usr/bin/env python3
"""Aggregate ingredients from 1..n recipes into a grocery list.

Usage:
    python3 grocery_list.py RECIPE[@SERVINGS | :SCALE] [...]
                            [--store SLUG] [--include-optional] [--out PATH]
                            [--vault PATH] [--json]

  RECIPE           the recipe as written (its own `servings`).
  RECIPE@SERVINGS  make that many servings (yield units), e.g. chana-masala@8
                   doubles a 4-serving recipe; decimals are fine (@6, @2.5).
  RECIPE:SCALE     explicit multiplier, e.g. chana-masala:2 or :3/2.
  There is no default multiplier: every recipe's servings are printed, and
  invalid or duplicate recipe arguments are reported and skipped.
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
import math
import sys
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kitchen-wiki" / "scripts"))
from kitchen_vault import (  # noqa: E402
    INGREDIENT_CATEGORIES, dimension, find_vault, fmt_amount, fmt_qty, load_vault,
    norm_slug, parse_ingredient_line, plural, recipe_yield, to_base,
)


class RecipeArgError(ValueError):
    pass


def _positive(s: str, what: str) -> Fraction:
    try:
        x = Fraction(s.strip())
    except (ValueError, ZeroDivisionError):
        raise RecipeArgError(f"{what} {s.strip()!r} is not a number") from None
    if x <= 0:
        raise RecipeArgError(f"{what} must be positive (got {s.strip()!r})")
    return x


# count units that measure an amount rather than name what you buy: rounding
# "1 1/2 inches" of ginger up to "2 inches" isn't a useful shopping hint
MEASURING_COUNT_UNITS = {"inch", "pinch", "dash", "sprig", "clove", "drop", "handful",
                         "splash", "slice", "piece", "leaf", "stalk"}
# per-item flags that are quantity notes, not availability (kept off the availability section)
NON_AVAILABILITY_FLAGS = ("fractional amount", "recipe gives a range")


def parse_recipe_arg(s: str) -> tuple[str, str, Fraction | None]:
    """'slug' -> (slug, 'as-written', None); 'slug@8' -> (slug, 'servings', 8);
    'slug:3/2' -> (slug, 'scale', 3/2). Raises RecipeArgError on bad input."""
    s = s.strip()
    if "@" in s and ":" in s:
        raise RecipeArgError("use either @SERVINGS or :SCALE, not both")
    if "@" in s:
        slug, _, n = s.partition("@")
        mode, value = "servings", _positive(n, "servings")
    elif ":" in s:
        slug, _, x = s.partition(":")
        mode, value = "scale", _positive(x, "scale")
    else:
        slug, mode, value = s, "as-written", None
    slug = norm_slug(slug.strip().strip("[]"))
    if not slug:
        raise RecipeArgError("no recipe slug")
    return slug, mode, value


def fmt_exact(x: Fraction) -> str:
    """fmt_qty when it's exact (eighths or coarser), else the plain fraction."""
    return fmt_qty(x) if Fraction(x).limit_denominator(8) == x else str(x)


def _num_json(x: Fraction | None):
    if x is None:
        return None
    return int(x) if x.denominator == 1 else float(x)


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
    seen: dict[str, str] = {}  # slug -> first argument that named it
    for arg in recipe_args:
        try:
            slug, mode, value = parse_recipe_arg(arg)
        except RecipeArgError as e:
            problems.append(f"invalid recipe argument {arg!r}: {e} (skipped)")
            continue
        if slug in seen:
            problems.append(f"recipe '{slug}' given more than once ({seen[slug]!r}, {arg!r}); "
                            f"ambiguous, kept {seen[slug]!r} and skipped {arg!r}")
            continue
        seen[slug] = arg
        r = v.get(slug, "recipe")
        if r is None:
            problems.append(f"unknown recipe '{slug}' (skipped)")
            continue
        base, yield_unit = recipe_yield(r)
        if mode == "servings":
            if base is None:
                problems.append(f"{arg!r}: recipe '{slug}' has no valid `servings`, so it can't "
                                f"be scaled to {fmt_exact(value)} {yield_unit} (skipped); "
                                "add servings to the recipe or pass an explicit :SCALE")
                continue
            scale = value / base
        elif mode == "scale":
            scale = value
        else:
            scale = Fraction(1)
        made = base * scale if base is not None else None
        recipes_used.append({"recipe": slug, "title": r.title, "servings": _num_json(made),
                             "base_servings": _num_json(base), "yield_unit": yield_unit,
                             "scale": str(scale)})
        for line in r.meta.get("ingredients") or []:
            use = parse_ingredient_line(line)
            if use is None:
                problems.append(f"{slug}: ingredient line without [[link]]: {line!r}")
                continue
            if use.optional and not include_optional:
                continue
            it = items.setdefault(use.slug, {"amounts": {}, "units": {}, "untracked": False,
                                             "recipes": [], "notes": [], "ranged": False, "by_recipe": {}})
            if slug not in it["recipes"]:
                it["recipes"].append(slug)
            share = it["by_recipe"].setdefault(slug, {"amounts": {}, "units": {}, "untracked": False, "notes": []})
            if use.note:
                it["notes"].append(use.note)
                share["notes"].append(use.note)
            it["ranged"] |= use.ranged
            if use.qty is None:
                it["untracked"] = share["untracked"] = True  # "to taste", "a pinch of"...
                continue
            dim = dimension(use.unit)
            amount = to_base(use.qty * scale, use.unit)
            for acc in (it, share):
                acc["amounts"][dim] = acc["amounts"].get(dim, Fraction(0)) + amount
                acc["units"].setdefault(dim, set()).add(use.unit)

    stocked = set(store.meta_links("stocked")) if store else set()
    not_stocked = set(store.meta_links("not_stocked")) if store else set()

    rows = []
    for slug, it in items.items():
        ing = v.get(slug, "ingredient")
        amounts = _amount_parts(it)
        by_recipe = [{"recipe": r_slug, "amount": " + ".join(_amount_parts(sh)), "notes": sh["notes"]}
                     for r_slug, sh in it["by_recipe"].items()]
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
        for dim, total in it["amounts"].items():
            if (dim.startswith("count:") and total.denominator != 1
                    and dim.split(":", 1)[1] not in MEASURING_COUNT_UNITS):
                n, unit = math.ceil(total), dim.split(":", 1)[1]
                if unit and n > 1:
                    unit = plural(unit)
                flags.append(f"fractional amount; buy {n} {unit}".rstrip())
        rows.append({
            "ingredient": slug,
            "name": ing.title if ing else slug,
            "amount": " + ".join(amounts) if amounts else "",
            "category": category if category in INGREDIENT_CATEGORIES else "other",
            "staple": staple,
            "recipes": it["recipes"],
            "by_recipe": by_recipe,
            "notes": sorted(set(it["notes"])),
            "flags": flags,
            "find_at": (ing.meta_links("find_at") if ing else []),
        })

    order = {c: i for i, c in enumerate(INGREDIENT_CATEGORIES)}
    rows.sort(key=lambda r: (r["staple"], order.get(r["category"], 99), r["name"].lower()))
    return {"recipes": recipes_used, "store": store.slug if store else None,
            "items": rows, "problems": problems}


def _amount_parts(acc: dict) -> list[str]:
    """Rendered amounts for an aggregate (whole list, or one recipe's share)."""
    parts = [fmt_amount(total, dim, acc["units"][dim]) for dim, total in acc["amounts"].items()]
    if acc["untracked"]:
        parts.append("to taste / as needed")
    return parts


def _yield_text(n, unit: str) -> str:
    if n is None:
        return f"{unit} unknown"
    q = fmt_exact(Fraction(str(n)))
    if unit == "servings" and q == "1":
        unit = "serving"
    return f"{q} {unit}"


def servings_line(x: dict) -> str:
    """'8 servings (×2 of 4 as written)' / '4 servings (as written)'."""
    scale = Fraction(x["scale"])
    made = _yield_text(x["servings"], x["yield_unit"])
    if x["base_servings"] is None:
        how = "as written" if scale == 1 else f"×{fmt_exact(scale)} of as written"
        return f"{made} ({how}; recipe has no `servings`)"
    if scale == 1:
        return f"{made} (as written)"
    return f"{made} (×{fmt_exact(scale)} of {fmt_exact(Fraction(str(x['base_servings'])))} as written)"


def to_markdown(r: dict, today: str) -> str:
    out = ["---", "type: grocery-list", f"date: {today}"]
    out.append("recipes: [" + ", ".join(f'"[[{x["recipe"]}]]"' for x in r["recipes"]) + "]")
    if r["recipes"]:
        out.append("servings:")
        for x in r["recipes"]:
            n = "unknown" if x["servings"] is None else fmt_exact(Fraction(str(x["servings"])))
            unit = "" if x["yield_unit"] == "servings" else f" {x['yield_unit']}"
            out.append(f'  - "[[{x["recipe"]}]]: {n}{unit}"')
    if r["store"]:
        out.append(f'store: "[[{r["store"]}]]"')
    out += ["---", f"# Grocery list — {today}", "", "Recipes:"]
    out += [f"- [[{x['recipe']}]]: {servings_line(x)}" for x in r["recipes"]]

    def line(row):
        s = f"- [ ] **{row['name']}**"
        if row["amount"]:
            s += f" — {row['amount']}"
        if len(row["by_recipe"]) > 1:
            # shared item: show each recipe's share so a recipe can be dropped or portioned
            shares = []
            for sh in row["by_recipe"]:
                amount = sh["amount"]
                if amount == "to taste / as needed" and sh["notes"]:
                    amount = ""  # the note ("to taste", "for the pasta water") already says it
                part = f"[[{sh['recipe']}]] {amount}".rstrip()
                if sh["notes"]:
                    part += (", " if amount else " ") + "; ".join(sh["notes"])
                shares.append(part)
            s += f" ({' · '.join(shares)})"
        else:
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
    flagged = [(x["name"], [f for f in x["flags"] if not f.startswith(NON_AVAILABILITY_FLAGS)])
               for x in r["items"]]
    flagged = [(name, fs) for name, fs in flagged if fs]
    if flagged:
        out += ["", "## Availability flags"]
        out += [f"- {name}: {'; '.join(fs)}" for name, fs in flagged]
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
