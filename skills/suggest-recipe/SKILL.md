---
name: suggest-recipe
description: Suggests what to cook this week by rotating cuisines and recipes in least-recently-eaten order, deterministically, from the kitchen wiki and meal history. Also records meals that were cooked. Use when the user asks what to make or eat this week or tonight, wants a weekly recipe pick or meal rotation, or says they cooked or ate a recipe and it should be logged.
compatibility: Requires Python 3.10+ (standard library only) and the kitchen-wiki skill's scripts/kitchen_vault.py in the same skills directory.
metadata:
  version: "0.1"
---

# Suggest recipe

Picks the week's recipe with a deterministic LRU rotation over **cuisines first, then recipes
within the chosen cuisine**. Meal history lives in `mise/meals.md`.

## Algorithm (implemented in `scripts/suggest.py`)

1. **Eligible recipes:** every `wiki/recipes/*` page except those with `rotation: false`, those
   eaten within the last `--cooldown-days` (default 14), and anything passed to
   `--exclude-recipe`.
2. **Cuisine recency:** a cuisine's last-eaten date is the most recent `meals.md` entry for any
   recipe tagged with it. Never eaten counts as oldest. A fusion recipe counts for every cuisine
   it lists.
3. **Choose the cuisine** with the oldest last-eaten date that still has an eligible recipe.
4. **Choose the recipe** within that cuisine with the oldest last-eaten date (never-eaten
   recipes come first).
5. **Ties** are broken by `sha256("<ISO-year>-W<week>:<slug>")`. The result is stable for a given
   week and rotates between weeks. The same vault and the same `--date` always give the same
   answer.

## Suggest

```bash
python3 skills/suggest-recipe/scripts/suggest.py                 # this week's pick
python3 skills/suggest-recipe/scripts/suggest.py --count 3       # 3 picks from 3 different cuisines
python3 skills/suggest-recipe/scripts/suggest.py --date 2026-11-16 --exclude-cuisine italian
python3 skills/suggest-recipe/scripts/suggest.py --json          # for further processing
```

When you present the result:
- Lead with the pick, a link to the recipe page, total time, and the one-line summary from the
  page.
- Explain in one line why it was picked (e.g. "Mexican hasn't been on the table since Oct 2, the
  longest of any cuisine").
- Show the as-written yield from the script (`serves 4 as written`, `makes 48 cookies as
  written`). If it says `servings: not set`, say so and offer to fix the recipe page.
- Show the runner-ups if `--count > 1`, and offer the `grocery-list` skill for the chosen
  recipe(s).
- **Before shopping, ask how many servings to make of each pick** (in the recipe's
  `yield_unit`). There is no default: don't assume "as written" or 2x, and don't carry over a
  previous week's answer. Pass the answers to `grocery-list` as `slug@N` (e.g.
  `chana-masala@6`); "as written" is a valid answer and becomes plain `slug`.
- Run the script and report its pick. Don't override it with your own preference, since that
  would break determinism. If the user rejects the pick, re-run with `--exclude-recipe` or
  `--exclude-cuisine` and say what changed.
- If the script exits with code 2 (nothing eligible), tell the user and suggest a shorter
  `--cooldown-days` or ingesting more recipes.

## Log a meal

When the user says they cooked or ate something:

```bash
python3 skills/suggest-recipe/scripts/log_meal.py chana-masala --date 2026-11-14 --note "doubled the ginger"
```

- The script rejects unknown slugs and suggests close matches. If the dish has no page yet,
  offer to ingest it with the `kitchen-wiki` skill first, or log it with `--force`.
- Feedback about the dish itself ("too salty", "kids loved it", "rating 4") belongs on the
  recipe page (`## Notes`, `rating`), not just in the meal note. Update the page with the
  `kitchen-wiki` conventions.

## Weekly automation

The script is deterministic and non-interactive, so it can run on a schedule (cron, or Claude
Code's scheduled tasks), e.g. every Sunday:
`python3 skills/suggest-recipe/scripts/suggest.py --count 3`
