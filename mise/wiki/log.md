---
type: log
---
# Log

Append-only. Entry headings: `## [YYYY-MM-DD] <ingest|query|lint|edit> | <title>`.
Last entries: `grep "^## \[" mise/wiki/log.md | tail -5`

## [2026-11-14] edit | Initialize wiki with seed content
- Created the schema, index, overview, and log.
- Seeded 3 cuisines, 3 recipes, 20 ingredients, 3 equipment, 3 techniques, and 2 stores (tagged `seed`, from general knowledge).

## [2026-11-14] edit | schema: rename vault folder vault/ -> mise/
- Updated path references in CLAUDE.md, README, schema, all SKILL.md files, scripts, and .gitignore. "Vault" is still the term in code (`--vault`, `KITCHEN_VAULT`).

## [2026-11-14] edit | schema: capture workflow
- Added `capture.py` (links, YouTube, PDFs/images, pasted text -> raw/), references/capture.md (fallback order, PDF handling), and Web Clipper templates. Raw file naming: `YYYY-MM-DD-<slug>.md`.

## [2026-11-14] edit | schema: verification
- lint.py: body-vs-frontmatter edge check, source sources<->informs reciprocity, dangling frontmatter edges are now errors, unresolved [?] transcription warnings, raw_sha256 stamping (`lint.py --hash`).
- Added a unit test suite in tests/ (`python3 -m unittest discover -s tests`). Fixed parser bugs: apostrophes in unquoted values, comma-separated meal links, backslash round-trip.

## [2026-11-14] edit | schema: servings are first-class
- Recipes require `servings` (optional `yield_unit`). grocery_list.py takes `slug`, `slug@N`, or `slug:X` and states servings for every recipe; fractional count amounts are flagged. suggest.py shows servings as written. Ingest records servings from the source and keeps scaling advice under `### Scaling`.
- grocery_list.py: shared items show each recipe's share (scaled amount + prep note); JSON items carry `by_recipe`.

## [2026-11-14] edit | split cumin -> cumin-seeds, ground-cumin
- Schema rule: one ingredient page per thing you buy (whole vs ground spices, fresh vs dried herbs are separate pages; prep forms stay one page).
- Created [[cumin-seeds]], [[ground-cumin]] and deleted cumin. Relinked [[chana-masala]], [[black-bean-tacos]], [[indian]], [[mexican]], [[indian-grocery]], index, and overview.
