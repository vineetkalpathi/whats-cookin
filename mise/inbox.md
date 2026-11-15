---
type: inbox
---
# Inbox

Recipes and sources waiting on a manual step. Maintained by the kitchen-wiki skill.
When an item is done, check it off and point to the result: `- [x] ... → [[slug]] (YYYY-MM-DD)`.

## Needs capture
Sources the capture fallback order couldn't get. Each needs the user to clip, paste, or hand over a file.
Line format: `- [ ] YYYY-MM-DD · <proposed-slug> · <url or location> · <what failed> · needs: <what the user should do>`

- [ ] 2026-11-15 · asian-cabbage-salad · original blog post (URL unknown) · the captured PDF is an excerpt · needs: a re-capture of the full post. **The Ginger Peanut Dressing recipe is missing** — it is listed as an ingredient and called for in step 3 of [[asian-cabbage-salad]], but appears nowhere on the page, and the cabbage bullet's "see below for tips" points at tips that are also absent. The salad is not cookable as captured
- [x] 2026-11-14 · shakshuka · https://www.themediterraneandish.com/shakshuka-recipe/ · HTTP 403 (capture.py + web fetch) · clipped with Web Clipper → [[shakshuka]] (2026-11-15). **Still open:** the user adapts this recipe; their changes aren't recorded yet
- [x] 2026-11-14 · instant-pot-mexican-rice · https://tastesbetterfromscratch.com/instant-pot-mexican-rice/ · HTTP 403 (capture.py + web fetch) · clipped with Web Clipper → [[instant-pot-mexican-rice]] (2026-11-15)
- [x] 2026-11-14 · ammas-recipes · Google Drive PDFs · private Drive · provided locally in `ammas-recipes/`; all 17 captured to `raw/` (2026-11-15)

## Needs the family
Questions only Amma (or the recipe's author) can answer. The wiki pages say what is missing; these are the asks.

- [ ] 2026-11-15 · killu-bonda · **the source gives no method at all** — ingredients only, for both recipes on the page, with the rest of the page blank. The method on [[killu-bonda]] and [[onion-tomato-chutney]] was reconstructed from general cooking knowledge and is flagged as such on both pages. Needs: Amma's actual steps
- [ ] 2026-11-15 · killu-bonda · the vegetables are given as one combined "4/3 cup shredded cabbage, carrot, finely cut bell pepper". The split into 1/2 + 1/2 + 1/3 cup on [[killu-bonda]] is the wiki's. Also: "2 scoops of idli batter" and "1/2 spoon of baking soda" are undefined measures
- [ ] 2026-11-15 · thai-curry · the source quantifies only 3 of 21 ingredients. Every other amount on [[thai-curry]] was inferred at ingest and scaled to 4 servings. Needs: the real amounts, the tofu firmness, and which curry paste brand and colour
- [ ] 2026-11-15 · paneer-kathi-rolls · garlic is used in the filling step but is not in the source's ingredient list and has no quantity. Needs: how much
- [ ] 2026-11-15 · borscht · the ingredient list says 3-4 tbsp red wine vinegar, the method says "2/3 tbs". Also, one fresh tomato is listed but never explicitly added. Needs: which is right
- [ ] 2026-11-15 · almond-flour-cake · the PDF is a low-quality screenshot with black bands; the page carries **no title** and the gram weights are unreliable (1/2 cup caster sugar is printed as 124 g, which doesn't reconcile). Needs: a cleaner copy of the original, or confirmation of the weights
- [ ] 2026-11-15 · asparagus-soup · no quantity for the asparagus or the milk, and no yield. Needs: rough amounts
- [ ] 2026-11-15 · quinoa-salad, pasta-salad · the "Servings | Prep Time | Total Time" header is an unfilled template in both, and neither gives quantities. Needs: nothing urgent — they are genuinely template recipes — but a serving count would help the grocery list

## Needs a draft
Dishes the user cooks without a written recipe. Each needs the user to write (or talk through) a first version, which is captured as a `note` source.
Line format: `- [ ] YYYY-MM-DD · <proposed-slug> · <what the user said about it>`

- [ ] 2026-11-14 · chili · chipotle peppers, onion, garlic, red pepper, pinto beans, ...
- [x] 2026-11-14 · bean-filling · used for quesadillas, tacos, enchiladas · answered by Amma's PDF rather than a draft → [[bean-filling]] (2026-11-15)
- [ ] 2026-11-14 · kimchi-fried-rice · with a marinated soft-boiled egg
- [x] 2026-11-14 · veggie-pasta · varies the pasta type, sauce, and veggies · answered by Amma's "Pasta Gravy" PDF rather than a draft → [[veggie-pasta]] (2026-11-15)
- [ ] 2026-11-14 · shawarma-tofu · with red/white sauce, served as a gyro, Greek/Mediterranean salad, or rice bowl
