import json
import unittest

from _helpers import FIXTURE_VAULT, GROCERY_SCRIPTS, run_script, temp_vault

import grocery_list as gl

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
        self.assertEqual(data["recipes"], [{"recipe": "black-bean-tacos", "title": "Black Bean Tacos", "scale": "1"}])
        self.assertEqual(set(data["items"][0]), {"ingredient", "name", "amount", "category", "staple",
                                                 "recipes", "notes", "flags", "find_at"})
        p = run_script(SCRIPT, "nope", "--vault", FIXTURE_VAULT, "--json")
        self.assertEqual(p.returncode, 1)

    def test_out_writes_inside_given_vault(self):
        with temp_vault() as root:
            p = run_script(SCRIPT, "cacio-e-pepe", "--out", "lists/test.md", "--vault", root)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("**spaghetti** — 8 oz", (root / "lists" / "test.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
