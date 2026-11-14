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

## [2026-11-14] edit | schema: clarify ghee/butter and ambiguous aliases
- Rule: only forms made while cooking stay one page; items sold and stored separately (ghee vs butter) are separate pages. Aliases must be unambiguous.
- [[cilantro]]: alias `dhania` changed to `hara dhania` (plain dhania also means ground coriander).

## [2026-11-14] ingest | Recipe book: 4 linked recipes (batch)
From the user's recipe book note, linked recipes only. Unlinked house recipes and Amma's recipes deferred by the user. Shakshuka (themediterraneandish.com) and Instant Pot Mexican rice (tastesbetterfromscratch.com) **not captured**: HTTP 403 from capture.py and web fetch; waiting on a Web Clipper clip or paste.
- Raw: `2026-11-14-thai-beef-salad.md`, `2026-11-14-traditional-chana-masala-recipe-chole.md`, `2026-11-14-instant-pot-chana-masala-punjabi-chole.md`, `2026-11-14-creamy-udon-noodles-with-tofu-high-protein.md`
- Sources created: [[thai-beef-salad]], [[traditional-chana-masala-recipe-chole]], [[instant-pot-chana-masala-punjabi-chole]], [[creamy-udon-noodles-with-tofu-high-protein]]
- Recipes created: [[thai-tofu-salad]] (user makes it with tofu instead of beef), [[instant-pot-chana-masala]], [[creamy-udon-noodles]]. Recipe replaced: [[chana-masala]] (seed version replaced with the sourced traditional recipe; seed tag removed).
- Cuisines created: [[thai]], [[japanese]]. Updated: [[indian]] (spice profile, flavor principles, recipes).
- Ingredients created (34): [[dried-chickpeas]], [[black-tea]], [[ghee]], [[bay-leaf]], [[green-chili]], [[roma-tomato]], [[chana-masala-powder]], [[ground-turmeric]], [[kashmiri-chili-powder]], [[kasoori-methi]], [[ground-coriander]], [[thai-chili]], [[sugar]], [[fish-sauce]], [[extra-firm-tofu]], [[black-pepper]], [[mixed-greens]], [[cherry-tomatoes]], [[red-onion]], [[cucumber]], [[mint]], [[peanuts]], [[silken-tofu]], [[soy-sauce]], [[rice-vinegar]], [[chili-crisp]], [[dark-soy-sauce]], [[tomato-paste]], [[nutritional-yeast]], [[garlic-powder]], [[smoked-paprika]], [[udon-noodles]], [[scallion]], [[sesame-seeds]]
- Ingredients updated: [[onion]], [[garlic]], [[ginger]], [[kosher-salt]], [[cilantro]], [[cumin-seeds]], [[garam-masala]], [[lime]], [[neutral-oil]], [[chickpeas]]; back-references to the old seed chana-masala removed from [[asafoetida]], [[crushed-tomatoes]].
- Equipment created: [[instant-pot]] (owned), [[mortar-and-pestle]], [[blender]] (ownership unknown). Updated: [[skillet]], [[chefs-knife]], [[dutch-oven]].
- Techniques created: [[pressure-cooking]], [[searing]]. Updated: [[blooming-spices]].
- Stores updated: [[indian-grocery]] (stocks), [[trader-joes]] (typically doesn't stock) for [[chana-masala-powder]], [[kashmiri-chili-powder]], [[kasoori-methi]].
- Updated [[overview]] and the index.

## [2026-11-14] edit | user preferences: equipment, chole, fish sauce
- User statements: owns a blender, doesn't own a mortar and pestle; considers chole and chana masala the same dish but keeps both recipes for now; replaces fish sauce.
- [[blender]] `owned: true`, [[mortar-and-pestle]] `owned: false`.
- [[thai-tofu-salad]]: [[fish-sauce]] -> [[soy-sauce]] (now vegan), dressing method uses the knife paste instead of the mortar.
- Updated [[fish-sauce]] (user note, vegan fish sauce substitute), [[soy-sauce]], [[overview]], and the index.

## [2026-11-14] edit | schema: inbox for manual steps
- Added `mise/inbox.md` (outside wiki/, like meals.md): `## Needs capture` for sources the capture fallback order couldn't get, `## Needs a draft` for dishes the user cooks without a written recipe. Done items are checked off with a link to the result.
- kitchen-wiki SKILL.md (ingest), references/capture.md (fallback table, PDFs), schema.md (vault layout), and CLAUDE.md updated.
- Seeded with shakshuka, instant-pot-mexican-rice, Amma's recipes (capture) and chili, bean-filling, kimchi-fried-rice, veggie-pasta, shawarma-tofu (draft). Updated [[overview]].
