---
name: grocery-list
description: Builds a consolidated grocery list from one or more recipes in the kitchen wiki, summing quantities across recipes, grouping by store section, separating pantry staples, and flagging items a given store (e.g. Trader Joe's) probably doesn't carry. Use when the user picks recipes to cook and wants a shopping list, asks what to buy, or asks whether a store will have the ingredients.
compatibility: Requires Python 3.10+ (standard library only) and the kitchen-wiki skill's scripts/kitchen_vault.py in the same skills directory.
metadata:
  version: "0.1"
---

# Grocery list

## Steps

1. **Resolve recipes.** Map what the user said to recipe slugs (`ls mise/wiki/recipes/`).
   Ask about scaling if it's unclear ("doubling for guests?"). If a recipe has no page, offer to
   ingest it first with the `kitchen-wiki` skill. The list is only as good as the recipe's
   `ingredients` lines.
2. **Resolve the store.** Use the store the user names. Otherwise use the one they've used
   before (check recent `mise/lists/` files), or leave it off. Store pages live in
   `mise/wiki/stores/`.
3. **Run the script:**
   ```bash
   python3 skills/grocery-list/scripts/grocery_list.py chana-masala black-bean-tacos:2 \
       --store trader-joes --out lists/2026-11-14.md
   ```
   - `slug:2` scales a recipe. `--include-optional` adds the `(optional)` ingredients.
   - `--json` gives structured output if you need to post-process it.
4. **Review the list before showing it.** The script is mechanical, so add your own judgment:
   - **Availability:** the script flags items in the store's `not_stocked` and `specialty` items
     the store isn't known to carry. Also read the store page's `## General patterns` and flag
     anything else likely to be missing (e.g. fresh curry leaves at Trader Joe's). Mark these as
     your judgment, not confirmed, and suggest alternatives: the ingredient's `find_at` stores,
     or a substitute from its `substitutes`.
   - **Purchase units:** turn odd totals into what you'd actually buy ("3 tbsp cilantro" → "1
     bunch cilantro").
   - **Overlap:** point out ingredients shared across recipes (that's the payoff of batching).
   - **Problems section:** unknown recipes or unlinked ingredient lines mean the wiki needs a
     fix. Offer to fix it.
5. **Present** the list grouped by section, with staples under "check the pantry first", then
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
