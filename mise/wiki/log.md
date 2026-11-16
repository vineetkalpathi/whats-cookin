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

## [2026-11-15] ingest | Clippings (shakshuka, IP Mexican rice) + Amma's recipes (17 PDFs captured, 2 ingested)
Cleared all three `## Needs capture` inbox items. The user clipped the two 403'd pages with Web Clipper into `mise/clippings/`, and put Amma's Google Drive PDFs in `ammas-recipes/` at the repo root. Both `bean-filling` and `veggie-pasta` were queued under `## Needs a draft`; Amma's PDFs answered them, so they were ingested from the PDFs instead of drafted. Per the user, `pasta-gravy.pdf` is filed as [[veggie-pasta]].
- Raw captured (19): `2026-11-15-shakshuka-recipe-mediterranean-dish.md`, `2026-11-15-instant-pot-authentic-mexican-rice.md` (both `via: clipper`, body taken from the clippings verbatim), and 17 `kind: family` PDF captures from `ammas-recipes/`.
- **15 of Amma's PDFs are captured but not ingested**, awaiting the user's pick: almond-flour-cake, asian-cabbage-salad, asparagus-soup, borscht, killu-bonda, methi-lagaan, paneer-kathi-rolls, pasta-salad, quinoa-salad, tex-mex-salad, thai-coconut-butternut-squash-soup, thai-curry, tomato-mozzarella-panini, tomato-soup, yellow-moong-khichdi. Listed in `mise/inbox.md`.
- Sources created: [[shakshuka-recipe-mediterranean-dish]], [[instant-pot-authentic-mexican-rice]], [[ammas-bean-filling]], [[ammas-pasta-gravy]].
- Recipes created: [[shakshuka]], [[instant-pot-mexican-rice]], [[bean-filling]] (component, `rotation: false`), [[veggie-pasta]].
- Cuisines created: [[mediterranean]], [[middle-eastern]]. Updated: [[mexican]], [[italian]], [[indian]], [[thai]] (common ingredients).
- Ingredients created (19): [[tomato]], [[tomato-sauce]], [[egg]], [[bell-pepper]], [[sweet-paprika]], [[long-grain-white-rice]], [[tomato-bouillon]], [[carrot]], [[frozen-peas]], [[pinto-beans]], [[broccoli]], [[zucchini]], [[mushroom]], [[pickled-jalapenos]], [[sriracha]], [[taco-seasoning]], [[pasta]], [[pasta-sauce]], [[basil]].
- Ingredients updated: [[olive-oil]], [[onion]], [[garlic]], [[ground-coriander]], [[ground-cumin]], [[red-pepper-flakes]], [[kosher-salt]], [[black-pepper]], [[parsley]], [[mint]], [[neutral-oil]], [[black-beans]] (pinto substitute), [[cilantro]].
- Techniques created: [[poaching-eggs-in-sauce]], [[toasting-rice]], [[saute-to-bite]]. Updated: [[blooming-spices]], [[pressure-cooking]].
- Equipment updated: [[skillet]], [[instant-pot]].
- **Decisions made during this ingest:**
  - One [[bell-pepper]] page for all colours rather than per-colour pages; colour is ripeness and the recipes swap them freely. Recipes note the colour as a prep note.
  - Source slugs may differ from the recipe slug they inform, to keep slugs unique: [[shakshuka-recipe-mediterranean-dish]] / [[shakshuka]] and [[instant-pot-authentic-mexican-rice]] / [[instant-pot-mexican-rice]]. The two web clippings were re-captured under the longer slugs so each source page still matches its raw file.
  - [[tomato-bouillon]] carries a `> [!warning]` callout: most brands contain chicken, so [[instant-pot-mexican-rice]] is tagged `gluten-free` but **not** `vegetarian`.
  - `servings` is an estimate on [[bean-filling]] (6) and [[veggie-pasta]] (4); neither source gives a yield. Noted on both pages.
- Updated [[overview]] and the index.

## [2026-11-15] ingest | Amma's recipes: remaining 15 PDFs (batch)
The user asked for all 15 remaining `ammas-recipes` PDFs, captured on 2026-11-15, to be compiled into the wiki. 15 sources produced **16 recipes** — `killu-bonda.pdf` carries a chutney recipe alongside the bondas.

Transcription was fanned out to five subagents, each owning a disjoint set of `raw/` capture notes and barred from `mise/wiki/`; all page writes were then serialized through one generator so the reciprocal edges could be derived rather than hand-maintained. Body prose for the new ingredient, equipment and technique pages was fanned out again, over disjoint files, with frontmatter frozen.

- Sources created (15): [[ammas-yellow-moong-khichdi]], [[ammas-paneer-kathi-rolls]], [[ammas-methi-lagaan]], [[ammas-killu-bonda]], [[ammas-tomato-soup]], [[ammas-thai-curry]], [[ammas-thai-coconut-butternut-squash-soup]], [[ammas-asian-cabbage-salad]], [[ammas-asparagus-soup]], [[ammas-borscht]], [[ammas-tomato-mozzarella-panini]], [[ammas-tex-mex-salad]], [[ammas-quinoa-salad]], [[ammas-pasta-salad]], [[ammas-almond-flour-cake]].
- Recipes created (16): [[yellow-moong-khichdi]], [[paneer-kathi-rolls]], [[methi-lagaan]], [[killu-bonda]], [[onion-tomato-chutney]], [[tomato-soup]], [[thai-curry]], [[thai-coconut-butternut-squash-soup]], [[asian-cabbage-salad]], [[asparagus-soup]], [[borscht]], [[tomato-mozzarella-panini]], [[tex-mex-salad]], [[quinoa-salad]], [[pasta-salad]], [[almond-flour-cake]].
- Cuisines created: [[american]], [[russian-ukrainian]]. Updated: [[indian]], [[thai]], [[mexican]], [[italian]].
- Ingredients created (66). Equipment created: [[saucepan]], [[baking-dish]], [[cake-pan]], [[electric-mixer]], [[slow-cooker]], [[panini-press]].
- Techniques created: [[dry-roasting]], [[deep-frying]], [[caramelizing-onions]], [[frying-curry-paste]], [[toasting-nuts]], [[folding-egg-whites]].
- [[indian-grocery]] now stocks the 16 specialty South Asian items this batch introduced.
- Resolved the pre-existing dangling `[[butter]] <- ghee` link by creating [[butter]].

### Two sources are incomplete, and the wiki says so
- **[[ammas-killu-bonda]] gives no method for either of its recipes** — ingredients only, with the rest of the page verifiably blank, so nothing was lost in capture. [[killu-bonda]] and [[onion-tomato-chutney]] carry a `> [!warning]` callout saying their methods were reconstructed from general knowledge and are not the family's. Queued in `mise/inbox.md`.
- **[[ammas-asian-cabbage-salad]] is an excerpt.** The Ginger Peanut Dressing is listed as an ingredient and called for in the method, but its recipe is absent, as are the cabbage-slicing tips the page promises. [[asian-cabbage-salad]] is not cookable as captured; queued for a re-capture.

### Decisions taken while reconciling five agents' proposals
- Slug collisions resolved centrally: `moong-dal`/`yellow-moong-dal` -> [[yellow-moong-dal]]; `cabbage` split into [[green-cabbage]] and [[red-cabbage]], with the generic name aliased to green; `frozen-corn`/`sweet-corn` -> [[sweet-corn]]; [[all-purpose-flour]] categorised `baking` rather than `grains-pasta`.
- Dropped as one-off alternatives, recorded as recipe prose instead: `frozen-peas-and-carrots` (mapped to [[frozen-peas]] + [[carrot]]), `thai-green-curry-paste`, sunflower seeds, bagged coleslaw, eno, leek, avocado oil, caster sugar.
- Techniques: kept the six that a source actually teaches; dropped `thickening-with-flour`, `yogurt-marinade`, `blending-hot-soup` and `blanching` as single-use or not taught.
- Equipment: dropped `kadai` (use [[dutch-oven]]), `box-grater`, `immersion-blender`.
- **New cuisine [[american]]** was created rather than forcing five Western recipes onto an existing page; the page says plainly that it is a catch-all for this collection's home-cooking register, not a claim about American cuisine. [[tex-mex-salad]] went to [[mexican]] rather than a one-member `tex-mex` page.
- **[[russian-ukrainian]]** names both countries deliberately, though the source says "Russian Soup".
- `servings` is an estimate on 11 of the 16 recipes; every one says so in `## Notes`. Only [[tomato-soup]] (3 bottles), [[paneer-kathi-rolls]] (6) and [[yellow-moong-khichdi]] (2-3) state a yield.
- Quantities on [[thai-curry]] and [[asian-cabbage-salad]] were inferred at ingest; both pages carry a warning callout saying so.
- Updated [[overview]] and the index.
