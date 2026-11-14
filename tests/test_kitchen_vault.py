import unittest
from fractions import Fraction as F

from _helpers import FIXTURE_VAULT, temp_vault

import kitchen_vault as kv


class FrontmatterTests(unittest.TestCase):
    def test_scalars_lists_and_comments(self):
        fm = "\n".join([
            "type: recipe  # trailing comment",
            "# whole-line comment",
            "servings: 4",
            "ratio: 1.5",
            "rotation: false",
            "owned: true",
            "parent:",
            'title: "Dal # not a comment"',
            "quoted: 'it''s'",
            "diet: [vegan, gluten-free]",
            'cuisine: ["[[indian]]", "[[punjabi]]"]',
            'single: "[[indian]]"',
            "ingredients:",
            '  - "2 can [[chickpeas]], drained"',
            "  - plain item",
        ])
        d = kv.parse_frontmatter(fm)
        self.assertEqual(d["type"], "recipe")
        self.assertEqual(d["servings"], 4)
        self.assertEqual(d["ratio"], 1.5)
        self.assertIs(d["rotation"], False)
        self.assertIs(d["owned"], True)
        self.assertEqual(d["parent"], [])
        self.assertEqual(d["title"], "Dal # not a comment")
        self.assertEqual(d["quoted"], "it's")
        self.assertEqual(d["diet"], ["vegan", "gluten-free"])
        self.assertEqual(d["cuisine"], ["[[indian]]", "[[punjabi]]"])
        self.assertEqual(d["single"], "[[indian]]")
        self.assertEqual(d["ingredients"], ["2 can [[chickpeas]], drained", "plain item"])

    def test_nested_mapping_rejected(self):
        with self.assertRaises(kv.FrontmatterError):
            kv.parse_frontmatter("subs:\n  - item: lemon\n    qty: 2")
        with self.assertRaises(kv.FrontmatterError):
            kv.parse_frontmatter("meta:\n  key: value")

    def test_list_item_without_list_key_rejected(self):
        with self.assertRaises(kv.FrontmatterError):
            kv.parse_frontmatter("title: x\n  - y")

    def test_split_frontmatter(self):
        self.assertEqual(kv.split_frontmatter("---\na: 1\n---\nbody"), ("a: 1", "body"))
        self.assertEqual(kv.split_frontmatter("no fm"), (None, "no fm"))
        with self.assertRaises(kv.FrontmatterError):
            kv.split_frontmatter("---\na: 1\nbody without close")

    # Regression: _split_inline_list and _strip_comment once treated any apostrophe as an
    # opening quote, even mid-word. `[za'atar, zaatar]` comes back as one item, and
    # `title: Mom's dal # note` keeps the comment. YAML only quotes at the start of a scalar.
    def test_apostrophe_inside_unquoted_inline_list_item(self):
        self.assertEqual(kv.parse_frontmatter("aliases: [za'atar, zaatar]")["aliases"], ["za'atar", "zaatar"])


class LinkTests(unittest.TestCase):
    def test_links_in_variants(self):
        text = "see [[chickpeas|garbanzo]], [[indian#Spice profile]], [[recipes/chana-masala]] and [[x.md]]"
        self.assertEqual(kv.links_in(text), ["chickpeas", "indian", "chana-masala", "x"])
        self.assertEqual(kv.links_in(["[[a]]", ["[[b]]"], None, 3]), ["a", "b"])
        self.assertEqual(kv.links_in(None), [])

    def test_norm_slug(self):
        self.assertEqual(kv.norm_slug(" wiki/recipes/dal.md "), "dal")


class VaultTests(unittest.TestCase):
    def test_load_vault_types_and_get(self):
        v = kv.load_vault(FIXTURE_VAULT)
        self.assertEqual([p.slug for p in v.of_type("cuisine")], ["indian", "italian", "mexican"])
        self.assertIn("dal-tadka", [p.slug for p in v.of_type("recipe")])
        self.assertIsNotNone(v.get("recipes/dal-tadka.md", "recipe"))
        self.assertIsNone(v.get("dal-tadka", "ingredient"))
        self.assertEqual(v.get("chana-masala").meta_links("cuisine"), ["indian"])
        self.assertFalse(any(p.error for p in v.pages.values()))

    def test_bad_frontmatter_becomes_page_error(self):
        with temp_vault() as root:
            (root / "wiki" / "recipes" / "broken.md").write_text("---\ntitle: x\n", encoding="utf-8")
            page = kv.load_vault(root).get("broken")
            self.assertIn("never closed", page.error)


class AmountTests(unittest.TestCase):
    def test_parse_amount(self):
        cases = {
            "1 1/2 cups": (F(3, 2), "cup", False),
            "½ tsp": (F(1, 2), "tsp", False),
            "1½ tbsp": (F(3, 2), "tbsp", False),
            "2-3 clove": (F(3), "clove", True),
            "2 – 3": (F(3), "", True),
            "1 large": (F(1), "", False),
            "2 cans": (F(2), "can", False),
            "3 inches": (F(3), "inch", False),
            "2 fl oz": (F(2), "fl oz", False),
            "": (None, "", False),
        }
        for s, want in cases.items():
            with self.subTest(s=s):
                self.assertEqual(kv.parse_amount(s), want)

    def test_parse_ingredient_line(self):
        u = kv.parse_ingredient_line("2 can [[chickpeas]], drained (optional)")
        self.assertEqual((u.slug, u.qty, u.unit, u.note, u.optional), ("chickpeas", F(2), "can", "drained", True))
        salt = kv.parse_ingredient_line("[[kosher-salt]], to taste")
        self.assertIsNone(salt.qty)
        self.assertEqual(salt.note, "to taste")
        self.assertFalse(salt.optional)
        self.assertEqual(kv.parse_ingredient_line("1 small [[onion|onions]]").slug, "onion")
        self.assertIsNone(kv.parse_ingredient_line("salt to taste"))

    def test_dimension(self):
        self.assertEqual(kv.dimension("tbsp"), "volume")
        self.assertEqual(kv.dimension("lb"), "weight")
        self.assertEqual(kv.dimension("clove"), "count:clove")

    def test_fmt_amount(self):
        tbsp_tsp = kv.to_base(F(1), "tbsp") + kv.to_base(F(1), "tsp")
        self.assertEqual(kv.fmt_amount(tbsp_tsp, "volume", {"tbsp", "tsp"}), "1 1/3 tbsp")
        self.assertEqual(kv.fmt_amount(kv.to_base(F(250), "ml"), "volume", {"ml"}), "250 ml")
        self.assertEqual(kv.fmt_amount(kv.to_base(F(3), "tsp"), "volume", {"tsp"}), "3 tsp")
        lb_oz = kv.to_base(F(1), "lb") + kv.to_base(F(8), "oz")
        self.assertEqual(kv.fmt_amount(lb_oz, "weight", {"lb", "oz"}), "1 1/2 lb")
        self.assertEqual(kv.fmt_amount(F(18), "count:clove", {"clove"}), "18 cloves")
        self.assertEqual(kv.fmt_amount(F(1), "count:can", {"can"}), "1 can")
        self.assertEqual(kv.fmt_amount(F(2), "count:bunch", {"bunch"}), "2 bunches")
        self.assertEqual(kv.fmt_amount(F(2), "count:", {""}), "2")


class MealsTests(unittest.TestCase):
    def test_fixture_meals(self):
        meals = kv.load_meals(FIXTURE_VAULT)
        self.assertEqual(meals[0], ("2026-10-01", "cacio-e-pepe", "too much pepper"))
        self.assertNotIn("2026-11-10", [d for d, _, _ in meals])  # inside <!-- -->
        self.assertEqual(len(meals), 4)

    def test_multiple_links_and_comments(self):
        text = ("- 2026-01-01 [[dal-tadka]] [[rice]] — with rice\n"
                "* 2026-01-02 [[tacos]]\n"
                "<!-- - 2026-01-03 [[hidden]] -->\n"
                "not a meal [[x]]\n")
        with temp_vault(meals=text) as root:
            self.assertEqual(kv.load_meals(root), [
                ("2026-01-01", "dal-tadka", "with rice"),
                ("2026-01-01", "rice", "with rice"),
                ("2026-01-02", "tacos", ""),
            ])
            (root / "meals.md").unlink()
            self.assertEqual(kv.load_meals(root), [])

    # Regression: load_meals once stripped links then lstrip("—–-: "), which doesn't include
    # ",", so "[[a]], [[b]] — note" yields the note ", — note".
    def test_comma_separated_links_note(self):
        with temp_vault(meals="- 2026-01-01 [[dal-tadka]], [[rice]] — note\n") as root:
            self.assertEqual(kv.load_meals(root)[0][2], "note")


if __name__ == "__main__":
    unittest.main()
