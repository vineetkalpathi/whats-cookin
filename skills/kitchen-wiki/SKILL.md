---
name: kitchen-wiki
description: Maintains a persistent, interlinked Obsidian wiki of recipes, ingredients, equipment, techniques, cuisines (with spice profiles), and grocery stores. Use when the user shares a link (recipe website, YouTube, Instagram), a PDF or photo, or pasted text to add, or wants to add or ingest a recipe or cooking source (article, video, cookbook, family recipe), asks a cooking question that the wiki can answer (substitutions, what to make with X, how a technique works, what defines a cuisine), wants to file an answer back into the wiki, or asks to lint or health-check the kitchen knowledge base.
compatibility: Scripts need Python 3.10+ (standard library only). Designed for Claude Code or similar agents with file read/write access.
metadata:
  pattern: llm-wiki
  version: "0.1"
---

# Kitchen wiki

You maintain a cooking knowledge base, following the LLM-wiki pattern: raw sources go in,
and you compile them into a persistent, cross-linked wiki that gets richer with every source
and question. The user curates and asks. You do the summarizing, cross-referencing, and
bookkeeping.

- **Vault:** `mise/` at the repo root (an Obsidian vault). Override with `KITCHEN_VAULT`.
- **Raw sources:** `mise/raw/`. Immutable. Read them and never edit them.
- **Wiki:** `mise/wiki/`. You own it. Every page follows [the schema](references/schema.md).
  **Read the schema before your first edit in a session.**
- **Templates:** `assets/templates/<type>.md`. Copy one, fill it in, and delete placeholder lines.
- **Capture:** `scripts/capture.py` turns a link, file, or pasted text into a raw file. The
  fallback order, PDF handling, and Obsidian Web Clipper setup are in
  [references/capture.md](references/capture.md).

## Ground rules

1. **Never modify `mise/raw/`.** If a source needs a fix, note it on its `sources/` page.
2. **Edges are written on both ends in the same pass** (see the edge table in the schema). Adding
   `[[garlic]]` to a recipe means adding that recipe to `garlic.used_in` too.
3. **Unique slugs across the whole wiki.** Search before creating a page
   (`ls mise/wiki/*/ | grep -i <name>`, and check `aliases:` too) so you don't make duplicates
   like `scallion` and `green-onion`. Pick one slug and add the others as `aliases`. The reverse
   also applies: forms bought separately (whole vs. ground spice, fresh vs. dried herb) are
   separate pages, not one page with a prep note (schema: "One ingredient page per thing you
   buy").
4. **Cite.** Facts that come from a source link to its `sources/` page. If a new source
   contradicts an existing claim, keep both, attribute each one, and add a `> [!warning]
   Conflict` callout. Don't silently overwrite.
5. **Every operation updates `wiki/index.md` and appends to `wiki/log.md`** (formats are in the
   schema).
6. Set `updated:` to today on every page you touch.
7. Keep general cooking knowledge apart from what the user has said. User statements ("I don't
   own a wok", "we hate cilantro") go into the relevant page (`owned: false`, a note on
   `cilantro`) and get logged.

## Operations

### Ingest (a new source)

1. **Capture first, if needed.** If the user gave a link, a file path, or pasted text, save it to
   `mise/raw/` before anything else:
   ```bash
   python3 skills/kitchen-wiki/scripts/capture.py <url-or-path> --json
   ```
   **Never give up on a link.** If the script exits with an error code, follow the fallback
   order in [the capture reference](references/capture.md), and only ask the user to paste or
   clip as the last step. Exit code 5 means the source is already in `raw/`: ingest that file
   (or tell the user it's already in the wiki) instead of capturing it again. If the source is
   already in `raw/` (clipped or dropped there), skip this step.
2. **Read the capture.** For PDFs (especially multi-recipe ones) and scans, follow the PDF section
   of the capture reference. For YouTube captures, check `description_links` in the JSON output:
   if a written recipe is linked, offer to capture it too and treat the video as the technique
   source.
3. Give the user 3–6 key takeaways and ask what to emphasize. Skip this step if they asked for
   batch or unattended ingest.
4. Create `wiki/sources/<slug>.md`, using the same slug as the raw file minus the date, with
   `raw:` pointing to it. Stamp `raw_sha256` with `lint.py --hash <raw path>` after any
   placeholder filling.
5. Create or update the **recipe** page. Normalize ingredient lines to the schema format, using
   purchasable units where natural. Cite page numbers for PDF and book sources, and timestamps
   for videos.
   - **`servings` is required** (a positive number: how many the recipe makes *as written*).
     Take it from the source (the capture's `yield` / recipeYield, or the book's "Serves").
     A count of something other than servings sets `yield_unit` too: "48 cookies" →
     `servings: 48`, `yield_unit: cookies`. For a range ("4-6 servings") use the lower bound and
     note the range in `## Notes`. If the source gives none, estimate from the quantities and
     say in `## Notes` that it's an estimate, or ask the user.
   - **Scaling advice** from the source (brown in batches when doubling, don't scale salt,
     leavening or chile linearly, longer cook time, bigger pan) goes under `### Scaling` in
     `## Notes`, cited. When the user reports how a scaled batch went (e.g. a meal log note
     like "made 8, doubled"), add it there too, dated: `- 2026-11-14: made 8 servings; ...`.
6. For every ingredient, equipment item, technique, and cuisine the recipe references, update the
   page if it exists, or create it from the template if it doesn't. Add back-references, and add
   any new substitutes, tips, or cuisine spice-profile entries the source teaches. One source
   often touches 10–15 pages. That's expected.
7. Update the **cuisine** page synthesis: if the recipe uses a spice or base that isn't in
   `spice_profile` / `## Flavor principles` yet, add it. If it adds to the pattern, revise the
   prose.
8. If the source mentions store availability ("hard to find outside Indian groceries"), set the
   ingredient's `availability` and `find_at`, and update the store pages.
9. Update `index.md` and `overview.md` (when the big picture shifts), and append to `log.md`.
10. Run the lint script, fix what it reports for the pages you touched, and summarize the pages
   you created and updated for the user.

### Query

1. Read `wiki/index.md` and pick the relevant pages, then read those pages and follow links as
   needed. Use `grep -ril <term> mise/wiki` for anything the index misses.
2. Answer with `[[links]]` to the pages you used. Pick a format that fits: prose, a comparison
   table, a substitution matrix, a week plan.
3. If the answer is reusable (a comparison, a "what can I make with X" analysis, a cuisine
   primer), offer to file it as `wiki/analyses/<slug>.md`, and fold any new facts into the
   underlying pages. Log the query.
4. If the wiki can't answer, say so and suggest a source to ingest or a web search. Don't
   present outside knowledge as if it came from the wiki.

### Lint

```bash
python3 skills/kitchen-wiki/scripts/lint.py          # human-readable
python3 skills/kitchen-wiki/scripts/lint.py --json   # machine-readable
```

The script checks: frontmatter syntax, required fields, type/folder agreement, duplicate slugs,
ingredient lines without links, frontmatter edges pointing at missing pages (error), raw files
changed since ingest (`raw_sha256` mismatch, error), missing reciprocal edges (including
`sources` ↔ `informs`), stale back-references, body links missing from frontmatter edges,
unresolved `[?]` marks in raw transcriptions, missing or unstamped raw files, other links to
pages that don't exist yet, orphans, and pages missing from the index. Exit code 1 means hard
errors.

Fix the mechanical issues yourself. Then do a judgment pass the script can't:
- contradictions between pages, or claims a newer source has superseded
- cuisine pages whose `spice_profile` no longer reflects their recipes
- ingredients that are probably duplicates under different names
- concepts that keep coming up but have no page (e.g. a technique mentioned in 4 recipes)
- suggestions for questions to explore or sources to find

Log the pass as `## [date] lint | <summary>`.

## Related skills

- `suggest-recipe` reads `wiki/recipes/*` (`cuisine`, `rotation`) and `mise/meals.md`.
- `grocery-list` reads recipe `ingredients`, ingredient `category` / `staple` / `availability` /
  `find_at`, and store `stocked` / `not_stocked`.

Keep those fields accurate when you ingest. Those skills depend on them.
