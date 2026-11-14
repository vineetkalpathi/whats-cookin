# whats-cookin

A personal kitchen knowledge base that an LLM agent maintains: recipes, ingredients, equipment,
techniques, and cuisines (with spice profiles), stored as an interlinked Obsidian wiki. The agent
also has skills for weekly recipe suggestions and grocery lists.

## Quick start
1. Open `mise/` as a vault in Obsidian (*Open folder as vault*). The graph view is color-coded by
   page type.
2. Start Claude Code (or another agent that reads `AGENTS.md`) in this repo, and try:
   - *"Ingest this recipe: <url or pasted text>"*, or drop a file in `mise/raw/` and say *"ingest raw/<file>"*
   - *"What can I substitute for asafoetida?"* / *"What defines Mexican spice profiles?"*
   - *"What should I cook this week?"*, then *"We made it, log it"*
   - *"Make a grocery list for chana masala and tacos, Trader Joe's"*
   - *"Lint the wiki"*

## Graph model
Nodes: **recipes, ingredients, equipment, techniques, cuisines**, plus stores, sources, and analyses.
Edges (stored in frontmatter, with back-references on both ends):
ingredient→recipe, equipment→recipe, technique→recipe, recipe→cuisine, ingredient→cuisine,
equipment↔technique, ingredient→substitute, store→ingredient availability.
Full spec: [`skills/kitchen-wiki/references/schema.md`](skills/kitchen-wiki/references/schema.md).

## Skills
| Skill | What it does | Script |
|---|---|---|
| `kitchen-wiki` | capture links/PDFs/videos, ingest sources, answer queries, lint | `scripts/capture.py`, `scripts/lint.py` |
| `suggest-recipe` | least-recently-eaten cuisine → least-recently-eaten recipe, deterministic weekly tie-break | `scripts/suggest.py`, `scripts/log_meal.py` |
| `grocery-list` | sums quantities across recipes, groups by store section, flags store availability | `scripts/grocery_list.py` |

All scripts use only the Python 3.10+ standard library. Optional: `yt-dlp` for YouTube transcripts (`brew install yt-dlp`).

**Web Clipper (optional):** for paywalled or logged-in sites, import the templates in `skills/kitchen-wiki/assets/web-clipper-*.json` into Obsidian Web Clipper. Setup is in [`references/capture.md`](skills/kitchen-wiki/references/capture.md).

## Roadmap
- Pantry and fridge inventory from photos, receipts, and user input, so grocery lists skip items on hand
- Search tooling (e.g. `qmd`) once the wiki outgrows `index.md`
