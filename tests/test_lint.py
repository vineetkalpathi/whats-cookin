"""Tests for skills/kitchen-wiki/scripts/lint.py. Stdlib unittest only.

Each test builds a tiny throwaway vault (wiki/ + raw/) in a temp dir.
Run: python3 -m unittest discover -s tests
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "kitchen-wiki" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import lint  # noqa: E402


def fm(**meta) -> str:
    """Render frontmatter in the schema's YAML subset. Lists become block lists."""
    lines = ["---"]
    for k, val in meta.items():
        if isinstance(val, list):
            lines.append(f"{k}:" if val else f"{k}: []")
            lines.extend(f'  - "{x}"' for x in val)
        else:
            lines.append(f"{k}: {val}")
    lines.append("---")
    return "\n".join(lines) + "\n"


class VaultCase(unittest.TestCase):
    """Base: a minimal consistent vault (one recipe, its ingredient and cuisine)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "wiki").mkdir()
        (self.root / "raw").mkdir()
        self.page("recipes/toast", fm(
            type="recipe", title="Toast", servings=2, cuisine=["[[british]]"],
            ingredients=["2 slice [[bread]]"]), "Toast the [[bread]].")
        self.page("ingredients/bread", fm(
            type="ingredient", title="Bread", category="bakery", used_in=["[[toast]]"]))
        self.page("cuisines/british", fm(type="cuisine", title="British", recipes=["[[toast]]"]))

    def tearDown(self):
        self._tmp.cleanup()

    def page(self, rel: str, frontmatter: str, body: str = "") -> Path:
        path = self.root / "wiki" / f"{rel}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter + body + "\n", encoding="utf-8")
        return path

    def raw(self, name: str, text: str) -> Path:
        path = self.root / "raw" / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_lint(self) -> dict:
        index_links = " ".join(f"[[{p.stem}]]" for p in (self.root / "wiki").rglob("*.md")
                               if p.stem != "index")
        (self.root / "wiki" / "index.md").write_text(f"# Index\n{index_links}\n", encoding="utf-8")
        return lint.lint(self.root)

    def assertMentions(self, items, *needles):
        hits = [it for it in items if all(n in it for n in needles)]
        self.assertTrue(hits, f"no item mentions {needles}: {items}")


class TestBaseline(VaultCase):
    def test_clean_vault(self):
        r = self.run_lint()
        for key in ("errors", "warnings", "missing_reciprocal_edges",
                    "body_links_missing_from_edges", "unresolved_transcriptions"):
            self.assertEqual(r[key], [], key)
        self.assertEqual(r["missing_pages"], {})


class TestExistingRules(VaultCase):
    def test_missing_reciprocal_edge(self):
        self.page("ingredients/bread", fm(type="ingredient", title="Bread", category="bakery"))
        r = self.run_lint()
        self.assertMentions(r["missing_reciprocal_edges"], "toast.ingredients", "[[bread]]")
        self.assertEqual(r["errors"], [])

    def test_duplicate_slug(self):
        self.page("recipes/bread", fm(type="recipe", title="Bread", servings=1, cuisine=["[[british]]"],
                                      ingredients=["1 [[bread]]"]))
        self.assertMentions(self.run_lint()["errors"], "duplicate slug 'bread'")

    def test_frontmatter_error(self):
        self.page("ingredients/butter", "---\ntype: ingredient\n  nested: x\n---\n")
        self.assertMentions(self.run_lint()["errors"], "butter.md", "frontmatter")

    def test_type_folder_mismatch(self):
        self.page("equipment/toaster", fm(type="technique", title="Toaster"))
        self.assertMentions(self.run_lint()["errors"], "toaster.md", "type should be 'equipment'")


class TestBodyEdges(VaultCase):
    def test_recipe_body_link_missing_from_frontmatter(self):
        self.page("techniques/toasting", fm(type="technique", title="Toasting", used_in=["[[toast]]"]))
        self.page("recipes/toast", fm(
            type="recipe", title="Toast", servings=2, cuisine=["[[british]]"],
            ingredients=["2 slice [[bread]]"]), "Toast the [[bread]] ([[toasting]]).")
        r = self.run_lint()
        self.assertMentions(r["body_links_missing_from_edges"],
                            "toast: body links [[toasting]] (technique)", "techniques")
        self.assertEqual(r["errors"], [])

    def test_recipe_body_link_present_in_frontmatter(self):
        self.page("techniques/toasting", fm(type="technique", title="Toasting", used_in=["[[toast]]"]))
        self.page("recipes/toast", fm(
            type="recipe", title="Toast", servings=2, cuisine=["[[british]]"],
            ingredients=["2 slice [[bread]]"], techniques=["[[toasting]]"]),
            "Toast the [[bread]] ([[toasting]]), see [[british]].")
        self.assertEqual(self.run_lint()["body_links_missing_from_edges"], [])

    def test_technique_body_links_equipment(self):
        self.page("equipment/toaster", fm(type="equipment", title="Toaster"))
        self.page("techniques/toasting", fm(type="technique", title="Toasting"),
                  "Use a [[toaster]].")
        self.assertMentions(self.run_lint()["body_links_missing_from_edges"],
                            "toasting: body links [[toaster]] (equipment)", "equipment")


class TestSourceBacklinks(VaultCase):
    def add_source(self, informs):
        self.raw("2026-01-01-toast.md", "toast recipe\n")
        self.page("sources/toast-src", fm(type="source", title="Toast src",
                                          raw='"raw/2026-01-01-toast.md"', informs=informs))

    def test_sources_without_informs(self):
        self.add_source([])
        self.page("ingredients/bread", fm(type="ingredient", title="Bread", category="bakery",
                                          used_in=["[[toast]]"], sources=["[[toast-src]] p. 3"]))
        self.assertMentions(self.run_lint()["missing_reciprocal_edges"],
                            "bread.sources -> [[toast-src]]", "informs")

    def test_informs_without_sources(self):
        self.add_source(["[[bread]]"])
        self.assertMentions(self.run_lint()["missing_reciprocal_edges"],
                            "toast-src.informs -> [[bread]]", "bread.sources")

    def test_both_directions_ok(self):
        self.add_source(["[[bread]]"])
        self.page("ingredients/bread", fm(type="ingredient", title="Bread", category="bakery",
                                          used_in=["[[toast]]"], sources=["[[toast-src]]"]))
        self.assertEqual(self.run_lint()["missing_reciprocal_edges"], [])


class TestDanglingEdges(VaultCase):
    def test_edge_key_dangling_is_error(self):
        self.page("recipes/toast", fm(
            type="recipe", title="Toast", servings=2, cuisine=["[[british]]"],
            ingredients=["2 slice [[bread]]", "1 tbsp [[butter]]"]), "")
        r = self.run_lint()
        self.assertMentions(r["errors"], "toast.md", "ingredients", "[[butter]]")
        self.assertNotIn("butter", r["missing_pages"])

    def test_body_and_substitute_dangling_stay_warnings(self):
        self.page("ingredients/bread", fm(
            type="ingredient", title="Bread", category="bakery", used_in=["[[toast]]"],
            substitutes=["[[brioche]]: 1:1"]), "Try [[sourdough]].")
        r = self.run_lint()
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["missing_pages"], {"brioche": ["bread"], "sourdough": ["bread"]})


class TestRawFiles(VaultCase):
    def source(self, raw="raw/2026-01-01-toast.md", **extra):
        self.page("sources/toast-src", fm(type="source", title="Toast src", raw=f'"{raw}"',
                                          informs=["[[toast]]"], **extra))
        self.page("recipes/toast", fm(
            type="recipe", title="Toast", servings=2, cuisine=["[[british]]"],
            ingredients=["2 slice [[bread]]"], sources=["[[toast-src]]"]), "")

    def test_unresolved_marks(self):
        p = self.raw("2026-01-01-toast.md", "2 [?] bread, 1 [?] butter\n")
        self.source(raw_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        r = self.run_lint()
        self.assertMentions(r["unresolved_transcriptions"], "toast-src", "2 unresolved", "[[toast]]")
        self.assertEqual(r["warnings"], [])

    def test_missing_raw_file_warns(self):
        self.source(raw="raw/nope.md")
        r = self.run_lint()
        self.assertMentions(r["warnings"], "toast-src.md", "doesn't exist")
        self.assertEqual(r["errors"], [])

    def test_unstamped_warns(self):
        self.raw("2026-01-01-toast.md", "clean\n")
        self.source()
        r = self.run_lint()
        self.assertMentions(r["warnings"], "not stamped")
        self.assertEqual(r["unresolved_transcriptions"], [])

    def test_hash_match_and_mismatch(self):
        p = self.raw("2026-01-01-toast.md", "original\n")
        self.source(raw_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(self.run_lint()["errors"], [])
        p.write_text("edited\n", encoding="utf-8")
        self.assertMentions(self.run_lint()["errors"], "toast-src.md", "raw file changed since ingest")


class TestServings(VaultCase):
    def toast(self, **extra):
        meta = dict(type="recipe", title="Toast", cuisine=["[[british]]"],
                    ingredients=["2 slice [[bread]]"])
        meta.update(extra)
        self.page("recipes/toast", fm(**meta), "Toast the [[bread]].")

    def test_missing_servings_is_error(self):
        self.toast()
        self.assertMentions(self.run_lint()["errors"], "toast.md", "missing required field 'servings'")

    def test_invalid_servings_are_errors(self):
        for bad in ("0", "-2", "lots", '"4"', "true"):
            with self.subTest(servings=bad):
                self.toast(servings=bad)
                self.assertMentions(self.run_lint()["errors"], "toast.md",
                                    "servings must be a positive number")

    def test_valid_servings_and_yield_unit_pass(self):
        for good in ({"servings": 4}, {"servings": 1.5}, {"servings": 24, "yield_unit": "cookies"}):
            with self.subTest(**good):
                self.toast(**good)
                self.assertEqual(self.run_lint()["errors"], [])

    def test_yield_unit_must_be_nonempty_string(self):
        for bad in ("12", "true", '""'):
            with self.subTest(yield_unit=bad):
                self.toast(servings=2, yield_unit=bad)
                self.assertMentions(self.run_lint()["errors"], "toast.md",
                                    "yield_unit must be a non-empty string")


class TestCLI(VaultCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "lint.py"), "--vault", str(self.root),
                               *args], capture_output=True, text=True)

    def test_exit_codes(self):
        self.run_lint()  # writes index.md
        self.assertEqual(self.cli().returncode, 0)
        self.page("equipment/toaster", fm(type="technique", title="Toaster"))
        res = self.cli("--json")
        self.assertEqual(res.returncode, 1)
        self.assertIn("body_links_missing_from_edges", res.stdout)

    def test_hash(self):
        p = self.raw("2026-01-01-toast.md", "hash me\n")
        want = hashlib.sha256(b"hash me\n").hexdigest()
        rel = self.cli("--hash", "raw/2026-01-01-toast.md")
        self.assertEqual((rel.returncode, rel.stdout.strip()), (0, want))
        self.assertEqual(self.cli("--hash", str(p)).stdout.strip(), want)
        self.assertEqual(self.cli("--hash", "raw/missing.md").returncode, 2)


if __name__ == "__main__":
    unittest.main()
