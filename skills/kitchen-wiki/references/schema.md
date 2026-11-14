# Kitchen wiki schema

The graph model, the page types, and the frontmatter rules. The scripts depend on this file, so
if you change a field name here, change the scripts too.

## Vault layout

```
mise/                      ← open this folder as the Obsidian vault
├── raw/                   immutable sources: YYYY-MM-DD-<slug>.md (+ same-stem PDF/image); never edit
│                          naming and header fields: references/capture.md
│   └── assets/            downloaded images
├── wiki/                  LLM-owned; every file follows this schema
│   ├── index.md           catalog of every page, by type, one line each
│   ├── log.md             append-only operation log
│   ├── overview.md        evolving synthesis: what this kitchen cooks, gaps, themes
│   ├── recipes/  ingredients/  equipment/  techniques/  cuisines/
│   ├── stores/            grocery stores + what they do / don't carry
│   ├── sources/           one summary page per raw source
│   └── analyses/          query answers worth keeping (comparisons, plans)
├── meals.md               meal history (what was eaten when), used by suggest-recipe
├── inbox.md               queue of manual steps: sources that need capture, dishes that need a draft
└── lists/                 generated grocery lists
```

## Slugs and links

- Filename = slug: lowercase, hyphenated, ASCII (`chana-masala.md`, `garam-masala.md`).
- **Slugs are unique across the whole wiki**, whatever the folder, so `[[slug]]` always resolves
  in Obsidian. If a name collides, qualify it: `paneer` (ingredient) vs `paneer-tikka` (recipe);
  `wok` (equipment) vs `wok-hei` (technique).
- Link with bare slugs: `[[chickpeas]]`, or `[[chickpeas|garbanzo beans]]` for display text.
- Singular ingredient names (`onion`, not `onions`), except for things that are only sold or used
  in the plural (`chickpeas`, `red-pepper-flakes`).
- **One ingredient page per thing you buy.** If two forms are bought separately, they get
  separate pages that list each other under `substitutes`: whole vs. ground spices
  (`cumin-seeds` / `ground-cumin`), fresh vs. dried herbs (`oregano` / `dried-oregano`), canned
  vs. dried beans, fresh vs. powdered ginger. Forms you make from one purchase *while cooking*
  stay one page with a prep note (`"4 clove [[garlic]], minced"` and `"..., thinly sliced"`;
  brown butter is `[[butter]]` plus a technique). Something sold and stored as its own item
  gets its own page even if it can be made at home: `ghee` is not `butter`. Aliases must not
  be ambiguous: `dhania` alone also means ground coriander seed, so `cilantro` uses
  `hara dhania`. The grocery
  list, pantry staples, and store availability all work per page, so this is what keeps them
  accurate.

## Graph model

| Edge | Stored on (forward) | Back-reference |
|---|---|---|
| ingredient → recipe | recipe `ingredients` | ingredient `used_in` |
| equipment → recipe | recipe `equipment` | equipment `used_in` |
| technique → recipe | recipe `techniques` | technique `used_in` |
| recipe → cuisine | recipe `cuisine` | cuisine `recipes` |
| ingredient → cuisine | ingredient `cuisines` | cuisine `common_ingredients` or `spice_profile` |
| equipment ↔ technique | equipment `techniques` | technique `equipment` |
| ingredient → substitute | ingredient `substitutes` | *(directional, no back-reference needed)* |
| equipment → substitute | equipment `substitutes` | *(directional)* |
| ingredient → store | store `stocked` / `not_stocked` | ingredient `find_at` (where to get specialty items) |
| page → source | any page's `sources` | source `informs` |

Both ends of a reciprocal edge get written in the same edit. `scripts/lint.py` reports any edge
that's missing its back-reference, and any back-reference whose forward edge is gone.

Edge keys must point at pages that exist: a dangling link in `ingredients`, `equipment`,
`techniques`, `cuisine`, `used_in`, `recipes`, `cuisines`, `common_ingredients`, `spice_profile`,
`stocked`, `not_stocked`, `find_at`, `sources`, `informs`, `parent` or `related` is a lint error
(create the page, even a stub, or drop the link). Links in the body or in `substitutes` may point
at pages that don't exist yet. A recipe whose body links an ingredient, equipment, technique or
cuisine page must also list it in the matching key (and a technique's body links to equipment
belong in its `equipment`).

## Frontmatter rules (a restricted YAML subset)

The scripts use only the Python standard library, so frontmatter is limited to:

- `key: scalar`: strings, numbers, `true`/`false`
- inline lists: `tags: [vegetarian, weeknight]`
- block lists of scalars:
  ```yaml
  ingredients:
    - "2 can [[chickpeas]], drained"
  ```
- **Quote every value that contains `[[links]]`.** Unquoted `[[x]]` is a nested list in YAML.
- **No nested mappings** (no `- item: x` / `qty: 2`). Structured data goes in one string,
  using the formats below. Obsidian's Properties view handles all of this, and the links show up
  in the graph.

### Ingredient line format (recipe `ingredients`)

```
"<quantity> <unit> [[ingredient-slug]], <prep note> (optional)"
```

- quantity: `2`, `1/2`, `1 1/2`, `½`, `2-3` (ranges use the upper bound when summing). Leave it out
  for "to taste": `"[[kosher-salt]], to taste"`.
- unit: `tsp tbsp cup ml l fl oz pint quart g kg oz lb` are converted and summed. Any other word
  (`can`, `clove`, `bunch`, `sprig`, `inch`) is a count unit, and only matching count units get
  summed. Size words (`large`, `small`) are ignored: `"1 large [[onion]]"` counts as 1 onion.
- Add `(optional)` to leave the line off grocery lists unless `--include-optional` is passed.
- Use the unit you'd buy in where it's natural (`1 can`, `1 bunch`). It makes grocery lists more
  useful.

### Substitute line format (ingredient / equipment `substitutes`)

```
"[[substitute-slug]]: <ratio>, <when it works / what changes>"
```
e.g. `"[[lemon]]: 1:1 juice, brighter, less floral"`.

## Page types

Every page has `type`, `title`, `tags` (may be empty), `sources` (links to `sources/` pages; may be
empty), and `updated: YYYY-MM-DD`.

### recipe (`wiki/recipes/`)
| field | req | notes |
|---|---|---|
| `cuisine` | ✓ | list of cuisine links. Fusion recipes list several |
| `ingredients` | ✓ | ingredient lines (format above) |
| `equipment` | | list of equipment links |
| `techniques` | | list of technique links |
| `servings` | ✓ | positive number (int or decimal): how many the recipe makes as written, in `yield_unit`s. Grocery lists scale from it (`slug@N`) |
| `yield_unit` | | plural noun when the yield isn't servings (`cookies`, `loaves`, `cups`); default `servings`. Non-empty string |
| `active_time`, `total_time` | | minutes (number) |
| `course` | | `main`, `side`, `breakfast`, `dessert`, `snack`, `drink`, `component` |
| `diet` | | e.g. `[vegetarian, vegan, gluten-free]` |
| `rotation` | | `false` keeps it out of weekly suggestions (holiday dishes, components) |
| `rating` | | 1–5, the user's own rating |

Body sections: summary line, `## Ingredients` (human-readable, with links), `## Method`
(numbered), `## Notes` (tips, variations, what went wrong last time; a `### Scaling`
subsection holds batch-cooking advice from sources and dated reports of scaled batches, and
servings estimates or ranges are noted here), `## Related`.

### ingredient (`wiki/ingredients/`)
| field | req | notes |
|---|---|---|
| `category` | ✓ | one of: produce, herbs, meat-seafood, dairy-eggs, bakery, grains-pasta, legumes, canned-jarred, spices, condiments-sauces, oils-vinegars, baking, nuts-seeds, frozen, beverages, other |
| `aliases` | | Obsidian aliases (`[garbanzo beans, chana]`) |
| `used_in` | | back-references to recipes |
| `cuisines` | | cuisines where it's characteristic |
| `substitutes` | | substitute lines |
| `staple` | | `true` = usually on hand; grocery lists put it under "check pantry" |
| `availability` | | `common` (default), `specialty` (ethnic/specialty grocer), `seasonal` |
| `find_at` | | store links where specialty items can be found |

Body: what it is, how to choose and store it, flavor, prep notes, `## Substitutes` (with context).

### equipment (`wiki/equipment/`)
Fields: `techniques`, `used_in`, `substitutes`, `owned` (`true`/`false`, does the user have one).
Body: what it's for, care, buying notes.

### technique (`wiki/techniques/`)
Fields: `equipment`, `used_in`, `related` (other technique links).
Body: what and why (the food science), steps, cues for when it's done, common mistakes.

### cuisine (`wiki/cuisines/`)
| field | notes |
|---|---|
| `region` | free text, e.g. `South Asia` |
| `parent` | link to a broader cuisine (`[[punjabi]]` → `"[[indian]]"`) |
| `spice_profile` | links to the characteristic spices/aromatics (ingredient pages) |
| `common_ingredients` | links to staple non-spice ingredients |
| `recipes` | back-references |

Body sections (this is where the **spice profile** lives):
- `## Flavor principles`: the base flavor combos (e.g. *tadka: cumin + mustard seed + chili in
  ghee*; *soffritto*; *sofrito*; *holy trinity*).
- `## Spice profile`: each key spice, how it's used (whole/ground, bloomed/toasted/finishing),
  common blends.
- `## Common ingredients`: produce, proteins, starches, fats, acids.
- `## Pantry starter kit`: the smallest set to buy to cook this cuisine at home.
- `## Recipes`: links.

### store (`wiki/stores/`)
| field | notes |
|---|---|
| `kind` | `grocery`, `specialty`, `warehouse`, `market`, `online` |
| `location` | free text (optional, the user's local branch) |
| `stocked` | ingredient links confirmed available (mostly for specialty items) |
| `not_stocked` | ingredient links confirmed (or typically) unavailable |

Body: general patterns (e.g. "Trader Joe's: small private-label range, few specialty spices,
herbs in clamshells"), so the agent can reason about items not listed yet.

### source (`wiki/sources/`)
Fields: `raw` (path under `raw/`, e.g. `"raw/2026-11-14-chana-masala.md"`), `url`, `author`,
`kind` (`article`, `video`, `book`, `photo`, `family`, `note`), `informs` (links to pages it fed),
`raw_sha256` (sha256 of the raw file, from `lint.py --hash <raw path>`; stamp it at ingest, after
filling any `## Contents` / `## Transcription` placeholders. Lint errors if the raw file changes
afterwards, and warns while it's unstamped or the transcription still has `[?]` marks).
Body: summary, key takeaways, claims that conflict with other sources.

### analysis (`wiki/analyses/`)
Fields: `question`, `informs` (pages it used). Body: the answer, with citations as links.

## index.md format

One section per type, alphabetical, one line per page:
```
- [[chana-masala]] - Punjabi chickpea curry; weeknight, vegan · indian
```

## log.md format

Append-only, newest at the bottom, with this heading prefix so it can be grepped:
```
## [YYYY-MM-DD] ingest | <source title>
## [YYYY-MM-DD] query | <question>
## [YYYY-MM-DD] lint | <summary>
## [YYYY-MM-DD] edit | <what changed>
```
Under each heading, list the pages created and updated.
