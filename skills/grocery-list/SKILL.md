---
name: grocery-list
description: Builds a consolidated grocery list from one or more recipes in the kitchen wiki, summing quantities across recipes, grouping by store section, separating pantry staples, and flagging items a given store (e.g. Trader Joe's) probably doesn't carry. Use when the user picks recipes to cook and wants a shopping list, asks what to buy, or asks whether a store will have the ingredients.
compatibility: Requires Python 3.10+ (standard library only) and the kitchen-wiki skill's scripts/kitchen_vault.py in the same skills directory.
metadata:
  version: "0.2"
---

# Grocery list

## Steps

1. **Resolve recipes.** Map what the user said to recipe slugs (`ls mise/wiki/recipes/`).
   If a recipe has no page, offer to ingest it first with the `kitchen-wiki` skill. The list is
   only as good as the recipe's `ingredients` lines.
2. **Confirm servings for every recipe.** Servings are first-class, and there is no default.
   Before running the script, state each recipe's as-written yield (its `servings` and
   `yield_unit`, e.g. "Chana Masala makes 4 servings as written") and confirm how many the user
   wants to make. Then pass `slug@N` (N servings, decimals fine), or the plain slug only if the
   user confirms "as written". Never assume a multiplier (no automatic 2x) and never carry one
   over from a previous list unless the user says so. If a recipe has no `servings`, ask, and
   fix the recipe page with `kitchen-wiki` (`@N` is rejected for it).
3. **Resolve the store.** Use the store the user names. Otherwise use the one they've used
   before (check recent `mise/lists/` files), or leave it off. Store pages live in
   `mise/wiki/stores/`.
4. **Run the script:**
   ```bash
   python3 skills/grocery-list/scripts/grocery_list.py chana-masala@8 black-bean-tacos \
       --store trader-joes --out lists/2026-11-14.md
   ```
   - `slug@8` makes 8 servings (×2 of a 4-serving recipe). Plain `slug` is as written.
     `slug:3/2` is an explicit multiplier, kept for back-compat; prefer `@N`.
   - Invalid arguments (`@0`, both `@` and `:`, unparseable numbers) and a recipe named twice
     are reported under Problems and skipped. Fix them and rerun; don't guess.
   - `--include-optional` adds the `(optional)` ingredients. `--json` gives structured output
     (each recipe has `servings`, `base_servings`, `yield_unit`, `scale`).
5. **Review the list before showing it.** The script is mechanical, so add your own judgment:
   - **Availability:** the script flags items in the store's `not_stocked` and `specialty` items
     the store isn't known to carry. Also read the store page's `## General patterns` and flag
     anything else likely to be missing (e.g. fresh curry leaves at Trader Joe's). Mark these as
     your judgment, not confirmed, and suggest alternatives: the ingredient's `find_at` stores,
     or a substitute from its `substitutes`.
   - **Purchase units:** turn odd totals into what you'd actually buy ("3 tbsp cilantro" → "1
     bunch cilantro"). Scaled count items that come out fractional are flagged
     (`fractional amount; buy 2 cans`).
   - **Overlap:** point out ingredients shared across recipes (that's the payoff of batching).
     Shared items show each recipe's share, e.g. `16 cloves ([[a]] 8 cloves, minced · [[b]] 2 cloves, ...)`.
     Keep the split when you present the list: it's how the user drops a recipe or portions
     for meal prep. It also exposes form differences, such as whole vs. ground cumin.
   - **Problems section:** unknown recipes or unlinked ingredient lines mean the wiki needs a
     fix. Offer to fix it.
6. **Present** the per-recipe servings lines first (`- [[chana-masala]]: 8 servings (×2 of 4 as
   written)`, as the script prints them), then the list grouped by section, with staples under "check the pantry first", then
   the flags.

## Learning from the store

When the user reports back ("TJ's didn't have asafoetida", "found paneer at TJ's!"):
- Add the ingredient to the store's `not_stocked` or `stocked`, plus a dated line under
  `## Confirmed observations`.
- If an item turned out to be easy to find, revisit its `availability`.
- Log it in `wiki/log.md` as `## [date] edit | store update: <store>`.

Each trip makes the flags more accurate.

## Future: pantry inventory

Planned: track fridge and pantry contents (from photos, receipts, and user input) so the list
can drop items already on hand. Until then, staples go in "check the pantry first", and the user
can say what they already have. Drop those items from the list you present.
