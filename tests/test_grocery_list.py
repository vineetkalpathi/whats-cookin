import json
import unittest

from _helpers import FIXTURE_VAULT, GROCERY_SCRIPTS, run_script, temp_vault

import grocery_list as gl
from kitchen_vault import parse_frontmatter, split_frontmatter

SCRIPT = GROCERY_SCRIPTS / "grocery_list.py"


def items(result):
    return {row["ingredient"]: row for row in result["items"]}


class GroceryListTests(unittest.TestCase):
    def test_aggregates_across_recipes(self):
        r = items(gl.build(FIXTURE_VAULT, ["chana-masala", "dal-tadka"], None, False))
        self.assertEqual(r["cumin"]["amount"], "1 1/3 tbsp")  # 1 tbsp + 1 tsp
        self.assertEqual(r["garlic"]["amount"], "6 cloves")   # 3 + (2-3 -> 3)
        self.assertIn("recipe gives a range; used the upper bound", r["garlic"]["flags"])
        self.assertEqual(r["onion"]["amount"], "2")           # size words ignored
        self.assertEqual(r["onion"]["recipes"], ["chana-masala", "dal-tadka"])
        self.assertEqual(r["kosher-salt"]["amount"], "to taste / as needed")

    def test_scaling(self):
        r = items(gl.build(FIXTURE_VAULT, ["chana-masala:2", "[[dal-tadka]]"], None, False))
        self.assertEqual(r["garlic"]["amount"], "9 cloves")
        self.assertEqual(r["cumin"]["amount"], "2 1/3 tbsp")
        self.assertEqual(r["chickpeas"]["amount"], "4 cans")

    def test_optional_excluded_unless_requested(self):
        self.assertNotIn("cilantro", items(gl.build(FIXTURE_VAULT, ["chana-masala"], None, False)))
        r = items(gl.build(FIXTURE_VAULT, ["chana-masala"], None, True))
        self.assertEqual(r["cilantro"]["amount"], "1/4 cup")

    def test_store_flags(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala", "dal-tadka", "cacio-e-pepe"], "trader-joes", False)
        self.assertEqual(r["problems"], [])
        rows = items(r)
        self.assertIn("not stocked at Trader Joe's", rows["red-lentils"]["flags"])
        self.assertIn("specialty item — may not be at Trader Joe's", rows["asafoetida"]["flags"])
        self.assertEqual(rows["pecorino"]["flags"], [])  # specialty but listed in stocked
        self.assertEqual(rows["chickpeas"]["flags"], [])

    def test_unknown_recipe_and_store_reported(self):
        r = gl.build(FIXTURE_VAULT, ["nope", "cacio-e-pepe"], "costco", False)
        self.assertEqual([x["recipe"] for x in r["recipes"]], ["cacio-e-pepe"])
        self.assertTrue(any("unknown recipe 'nope'" in p for p in r["problems"]))
        self.assertTrue(any("unknown store 'costco'" in p for p in r["problems"]))
        self.assertIsNone(r["store"])

    def test_staples_section_in_markdown(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala"], None, False)
        self.assertEqual([x["ingredient"] for x in r["items"] if x["staple"]], ["cumin", "kosher-salt"])
        md = gl.to_markdown(r, "2026-11-14")
        pantry = md.split("## Check the pantry first (staples)")[1]
        self.assertIn("**cumin**", pantry)
        self.assertNotIn("**cumin**", md.split("## Check the pantry first")[0])
        self.assertIn("**chickpeas** — 2 cans", md)

    def test_cli_json_shape_and_exit_codes(self):
        p = run_script(SCRIPT, "black-bean-tacos", "--store", "trader-joes", "--vault", FIXTURE_VAULT, "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertEqual(set(data), {"recipes", "store", "items", "problems"})
        self.assertEqual(data["recipes"], [{"recipe": "black-bean-tacos", "title": "Black Bean Tacos",
                                            "servings": 4, "base_servings": 4,
                                            "yield_unit": "servings", "scale": "1"}])
        self.assertEqual(set(data["items"][0]), {"ingredient", "name", "amount", "category", "staple",
                                                 "recipes", "by_recipe", "notes", "flags", "find_at"})
        p = run_script(SCRIPT, "nope", "--vault", FIXTURE_VAULT, "--json")
        self.assertEqual(p.returncode, 1)

    def test_out_writes_inside_given_vault(self):
        with temp_vault() as root:
            p = run_script(SCRIPT, "cacio-e-pepe", "--out", "lists/test.md", "--vault", root)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("**spaghetti** — 8 oz", (root / "lists" / "test.md").read_text(encoding="utf-8"))


class ServingsTests(unittest.TestCase):
    """Servings are explicit: every recipe states how many are being made."""

    def recipes(self, result):
        return {x["recipe"]: x for x in result["recipes"]}

    def test_as_written_line(self):
        md = gl.to_markdown(gl.build(FIXTURE_VAULT, ["chana-masala"], None, False), "2026-11-14")
        self.assertIn("- [[chana-masala]]: 4 servings (as written)", md)

    def test_at_n_scales_to_servings(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala@8", "cacio-e-pepe@3"], None, False)
        self.assertEqual(r["problems"], [])
        rec = self.recipes(r)
        self.assertEqual((rec["chana-masala"]["scale"], rec["chana-masala"]["servings"]), ("2", 8))
        self.assertEqual(rec["cacio-e-pepe"]["scale"], "3/2")  # 3 of 2
        self.assertEqual(items(r)["chickpeas"]["amount"], "4 cans")
        md = gl.to_markdown(r, "2026-11-14")
        self.assertIn("- [[chana-masala]]: 8 servings (×2 of 4 as written)", md)
        self.assertIn("- [[cacio-e-pepe]]: 3 servings (×1 1/2 of 2 as written)", md)

    def test_decimal_servings_and_fractional_purchase_flag(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala@6.0"], None, False)
        self.assertEqual(self.recipes(r)["chana-masala"]["scale"], "3/2")
        rows = items(r)
        self.assertEqual(rows["chickpeas"]["amount"], "3 cans")
        self.assertNotIn("fractional amount", " ".join(rows["chickpeas"]["flags"]))
        self.assertEqual(rows["onion"]["amount"], "1 1/2")
        self.assertIn("fractional amount; buy 2", rows["onion"]["flags"])
        # measuring units (cloves, inches, pinches...) aren't purchase units: no rounding hint
        self.assertEqual(rows["garlic"]["amount"], "4 1/2 cloves")
        self.assertNotIn("fractional amount", " ".join(rows["garlic"]["flags"]))
        # volume and weight never get the flag
        self.assertNotIn("fractional amount", " ".join(rows["cumin"]["flags"] + rows["asafoetida"]["flags"]))
        md = gl.to_markdown(r, "2026-11-14")
        self.assertIn("×1 1/2 of 4 as written", md)
        # rounding hints stay on the item line, not in the availability section
        self.assertIn("fractional amount; buy 2", md.split("## Availability flags")[0])
        self.assertNotIn("fractional amount", md.split("## Availability flags")[-1] if "## Availability flags" in md else "")

    def test_fractional_count_flag_uses_ceil(self):
        r = items(gl.build(FIXTURE_VAULT, ["black-bean-tacos@5"], None, False))  # ×5/4
        self.assertEqual(r["black-beans"]["amount"], "2 1/2 cans")
        self.assertIn("fractional amount; buy 3 cans", r["black-beans"]["flags"])
        self.assertEqual(r["corn-tortillas"]["amount"], "15")
        self.assertFalse(any("fractional" in f for f in r["corn-tortillas"]["flags"]))

    def test_explicit_scale_still_works(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala:3/2", "dal-tadka:2"], None, False)
        rec = self.recipes(r)
        self.assertEqual((rec["chana-masala"]["servings"], rec["dal-tadka"]["servings"]), (6, 8))
        self.assertIn("- [[dal-tadka]]: 8 servings (×2 of 4 as written)", gl.to_markdown(r, "2026-11-14"))

    def test_invalid_args_reported_and_skipped(self):
        args = ["chana-masala@0", "dal-tadka:-1", "cacio-e-pepe@x", "black-bean-tacos@4:2",
                "chana-masala:", "dal-tadka@1/0"]
        r = gl.build(FIXTURE_VAULT, args, None, False)
        self.assertEqual(r["recipes"], [])
        self.assertEqual(len(r["problems"]), len(args))
        for arg, problem in zip(args, r["problems"]):
            self.assertIn(f"invalid recipe argument {arg!r}", problem)
            self.assertIn("(skipped)", problem)
        self.assertIn("not both", r["problems"][3])

    def test_duplicate_recipe_is_a_problem(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala@8", "[[chana-masala]]"], None, False)
        self.assertEqual([(x["recipe"], x["servings"]) for x in r["recipes"]], [("chana-masala", 8)])
        self.assertTrue(any("given more than once" in p and "ambiguous" in p for p in r["problems"]))
        self.assertEqual(items(r)["chickpeas"]["amount"], "4 cans")

    def test_at_n_on_recipe_without_servings(self):
        with temp_vault() as root:
            path = root / "wiki" / "recipes" / "dal-tadka.md"
            path.write_text(path.read_text(encoding="utf-8").replace("servings: 4\n", ""), encoding="utf-8")
            r = gl.build(root, ["dal-tadka@8", "chana-masala"], None, False)
            self.assertEqual([x["recipe"] for x in r["recipes"]], ["chana-masala"])
            self.assertTrue(any("'dal-tadka@8'" in p and "no valid `servings`" in p for p in r["problems"]))
            # as written / explicit scale still work, with servings stated as unknown
            r = gl.build(root, ["dal-tadka:2"], None, False)
            self.assertEqual((r["recipes"][0]["servings"], r["recipes"][0]["base_servings"]), (None, None))
            self.assertIn("- [[dal-tadka]]: servings unknown (×2 of as written; recipe has no `servings`)",
                          gl.to_markdown(r, "2026-11-14"))

    def test_yield_unit(self):
        with temp_vault() as root:
            path = root / "wiki" / "recipes" / "black-bean-tacos.md"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "servings: 4\n", "servings: 12\nyield_unit: tacos\n"), encoding="utf-8")
            r = gl.build(root, ["black-bean-tacos@24"], None, False)
            self.assertEqual(r["recipes"][0]["yield_unit"], "tacos")
            md = gl.to_markdown(r, "2026-11-14")
            self.assertIn("- [[black-bean-tacos]]: 24 tacos (×2 of 12 as written)", md)
            self.assertIn('"[[black-bean-tacos]]: 24 tacos"', md)

    def test_frontmatter_servings_round_trip(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala@6", "dal-tadka", "cacio-e-pepe:3"], "trader-joes", False)
        fm_text, _ = split_frontmatter(gl.to_markdown(r, "2026-11-14"))
        meta = parse_frontmatter(fm_text)
        self.assertEqual(meta["servings"], ["[[chana-masala]]: 6", "[[dal-tadka]]: 4", "[[cacio-e-pepe]]: 6"])
        self.assertEqual(meta["recipes"], ["[[chana-masala]]", "[[dal-tadka]]", "[[cacio-e-pepe]]"])
        self.assertEqual(meta["store"], "[[trader-joes]]")

    def test_cli_at_n_json(self):
        p = run_script(SCRIPT, "chana-masala@6", "--vault", FIXTURE_VAULT, "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["recipes"], [
            {"recipe": "chana-masala", "title": "Chana Masala", "servings": 6, "base_servings": 4,
             "yield_unit": "servings", "scale": "3/2"}])
        p = run_script(SCRIPT, "chana-masala@0", "--vault", FIXTURE_VAULT)
        self.assertEqual(p.returncode, 1)
        self.assertIn("invalid recipe argument", p.stdout)


if __name__ == "__main__":
    unittest.main()


class PerRecipeBreakdownTests(unittest.TestCase):
    def test_shared_item_lists_each_recipes_share(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala@8", "black-bean-tacos"], None, False)
        shared = [x for x in r["items"] if len(x["by_recipe"]) > 1]
        self.assertTrue(shared, "fixture recipes should share at least one ingredient")
        row = shared[0]
        self.assertEqual([s["recipe"] for s in row["by_recipe"]], row["recipes"])
        md = gl.to_markdown(r, "2026-11-14")
        line = next(l for l in md.splitlines() if f"**{row['name']}**" in l)
        for share in row["by_recipe"]:
            self.assertIn(f"[[{share['recipe']}]] {share['amount']}".rstrip(), line)
        self.assertNotIn("for [[", line)

    def test_each_share_matches_that_recipe_built_alone(self):
        args = ["chana-masala@8", "black-bean-tacos"]
        combined = items(gl.build(FIXTURE_VAULT, args, None, False))
        alone = {a.split("@")[0]: items(gl.build(FIXTURE_VAULT, [a], None, False)) for a in args}
        checked = 0
        for slug, row in combined.items():
            if len(row["by_recipe"]) < 2:
                continue
            for share in row["by_recipe"]:
                self.assertEqual(share["amount"], alone[share["recipe"]][slug]["amount"], (slug, share))
                checked += 1
        self.assertGreater(checked, 0)

    def test_single_recipe_items_keep_compact_format(self):
        r = gl.build(FIXTURE_VAULT, ["chana-masala"], None, False)
        md = gl.to_markdown(r, "2026-11-14")
        self.assertIn("for [[chana-masala]]", md)
