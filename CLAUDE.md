# whats-cookin: kitchen knowledge agent

This repo is an agent for knowledge about recipes, ingredients, equipment, techniques, and
cuisines. It follows the LLM-wiki pattern ([docs/llm-wiki-karpathy.md](docs/llm-wiki-karpathy.md)):
the agent compiles raw sources into a persistent, interlinked Obsidian wiki and keeps it current.
Skills follow the Agent Skills spec ([docs/agent-skills-specification.md](docs/agent-skills-specification.md)).

## Layout
- `mise/`: **Obsidian vault** (open this folder in Obsidian)
  - `raw/`: immutable sources. Read them, never edit them
  - `wiki/`: agent-maintained pages (recipes, ingredients, equipment, techniques, cuisines, stores, sources, analyses) plus `index.md`, `log.md`, `overview.md`
  - `meals.md`: meal history (for recipe rotation)
  - `lists/`: generated grocery lists
- `skills/`: Agent Skills (`.claude/skills` symlinks here)
  - `kitchen-wiki`: capture / ingest / query / lint. **Owns the schema:** `skills/kitchen-wiki/references/schema.md`
  - `suggest-recipe`: deterministic LRU weekly suggestion, plus meal logging
  - `grocery-list`: aggregates recipes into a shopping list, with store availability flags
- `docs/`: background reading

## Rules
- Before editing anything under `mise/wiki/`, read `skills/kitchen-wiki/references/schema.md`, and follow the `kitchen-wiki` skill's ground rules (reciprocal edges, unique slugs, citations, index and log updates).
- Never modify `mise/raw/`.
- After wiki edits, run `python3 skills/kitchen-wiki/scripts/lint.py` and fix any errors.
- Scripts are Python 3.10+ standard library only. Keep it that way (no PyYAML), so the frontmatter subset in the schema stays the contract.
- Pages tagged `seed` were written from general knowledge when the repo was set up. Prefer sourced content, and revise or retag seed pages as real sources come in.
- This file and the schema evolve together. When a convention changes, update both, and log it as `## [date] edit | schema: ...`.
