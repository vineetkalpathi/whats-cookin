import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _helpers import KW_SCRIPTS, run_script, temp_vault

import capture
import kitchen_vault as kv

SCRIPT = KW_SCRIPTS / "capture.py"
HTML = (Path(__file__).resolve().parent / "fixtures" / "capture" / "recipe_page.html").read_text(encoding="utf-8")
DATE = "2026-11-14"

VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.500 align:start position:0%

today<00:00:00.500><c> we're</c><00:00:01.000><c> making</c><00:00:01.500><c> dal</c>

00:00:02.500 --> 00:00:02.510 align:start position:0%
today we're making dal
\x20

00:00:10.000 --> 00:00:12.000 align:start position:0%
today we're making dal
rinse<00:00:10.500><c> the</c><00:00:11.000><c> lentils</c>

00:00:31.000 --> 00:00:33.000 align:start position:0%
rinse the lentils
salt &amp; simmer

00:01:05.000 --> 00:01:07.000
bloom the cumin

1:00:00.000 --> 1:00:02.000
enjoy
"""


def capture_meta(path: Path) -> dict:
    fm, _ = kv.split_frontmatter(path.read_text(encoding="utf-8"))
    return kv.parse_frontmatter(fm)


class JsonLdTests(unittest.TestCase):
    def setUp(self):
        self.parser = capture._PageParser()
        self.parser.feed(HTML)

    def test_page_parser_and_find_recipe(self):
        self.assertEqual(len(self.parser.jsonld), 3)
        self.assertEqual(self.parser.meta["og:site_name"], "Example Kitchen")
        recipe = capture.find_recipe(self.parser.jsonld)  # skips Organization + bad JSON, walks @graph
        self.assertEqual(recipe["@type"], ["Recipe", "NewsArticle"])

    def test_find_recipe_none_and_other_shapes(self):
        self.assertIsNone(capture.find_recipe(['{"@type": "Article"}', "not json", '[{"@type": "WebPage"}]']))
        self.assertEqual(capture.find_recipe(['{"@type": "http://schema.org/Recipe", "name": "x"};'])["name"], "x")
        nested = '{"@type": "WebPage", "mainEntity": {"@type": "Recipe", "name": "y"}}'
        self.assertEqual(capture.find_recipe([nested])["name"], "y")

    def test_instructions(self):
        recipe = capture.find_recipe(self.parser.jsonld)
        self.assertEqual(capture.instructions_md(recipe["recipeInstructions"]),
                         ["\n**Dal**\n", "1. Rinse the lentils.", "2. Simmer 20 minutes.",
                          "\n**Tadka**\n", "3. Bloom cumin in ghee."])
        self.assertEqual(capture.instructions_md("Chop onions.<br>Fry them &amp; stir.\n\nServe."),
                         ["1. Chop onions.", "2. Fry them & stir.", "3. Serve."])
        self.assertEqual(capture.instructions_md(["Boil.", {"@type": "HowToStep", "name": "Drain."}, ""]),
                         ["1. Boil.", "2. Drain."])
        self.assertEqual(capture.instructions_md(None), [])

    def test_small_helpers(self):
        self.assertEqual(capture.image_url("https://e.com/a.jpg"), "https://e.com/a.jpg")
        self.assertEqual(capture.image_url(["https://e.com/a.jpg", "b.jpg"]), "https://e.com/a.jpg")
        self.assertEqual(capture.image_url({"contentUrl": "https://e.com/c.jpg"}), "https://e.com/c.jpg")
        self.assertIsNone(capture.image_url([]))
        self.assertEqual(capture.iso_minutes("PT1H30M"), 90)
        self.assertEqual(capture.iso_minutes("P0DT0H20M"), 20)
        self.assertIsNone(capture.iso_minutes("PT0S"))
        self.assertIsNone(capture.iso_minutes("20 minutes"))
        self.assertEqual(capture.text_of([{"name": "Asha"}, "Ravi &amp; co", None]), "Asha, Ravi & co")
        self.assertEqual(capture.clean("Mom&#39;s &amp;amp; <i>dal</i>"), "Mom's & dal")

    def test_capture_website_with_patched_fetch(self):
        args = types.SimpleNamespace(title=None, slug=None, date=DATE)
        with mock.patch.object(capture, "fetch", return_value=("https://example.com/dal", HTML)):
            meta, body, slug = capture.capture_website("https://example.com/dal", args)
        self.assertEqual(slug, "moms-dal-rice")
        self.assertEqual(meta["title"], "Mom's Dal & Rice")
        self.assertEqual((meta["author"], meta["published"], meta["yield"]), ("Asha, Ravi", "2024-03-05", "4"))
        self.assertEqual((meta["prep_time"], meta["cook_time"], meta["total_time"]), (10, 65, 75))
        self.assertEqual(meta["image"], "https://example.com/dal.jpg")
        self.assertIn('Weeknight "comfort" food.', body)
        self.assertIn("- 1 tsp cumin & mustard seeds", body)
        self.assertNotIn("[!warning]", body)

    def test_capture_website_without_recipe_raises_2(self):
        args = types.SimpleNamespace(title=None, slug=None, date=DATE)
        page = "<html><head><title>Blog post</title></head></html>"
        with mock.patch.object(capture, "fetch", return_value=("https://e.com/p", page)):
            with self.assertRaises(capture.CaptureError) as cm:
                capture.capture_website("https://e.com/p", args)
        self.assertEqual(cm.exception.code, 2)


class HelperTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(capture.slugify("Mom’s Chana Masala!"), "moms-chana-masala")
        self.assertEqual(capture.slugify("Grandma's Crème Brûlée"), "grandmas-creme-brulee")
        long = capture.slugify("word " * 40)
        self.assertLessEqual(len(long), 60)
        self.assertFalse(long.endswith("-"))
        self.assertEqual(capture.slugify("!!!"), "untitled")

    def test_parse_vtt(self):
        paras = capture.parse_vtt(VTT)
        self.assertEqual(paras, [
            "**[0:00]** today we're making dal rinse the lentils",
            "**[0:31]** salt & simmer",
            "**[1:05]** bloom the cumin",
            "**[1:00:00]** enjoy",
        ])


class CaptureCliTests(unittest.TestCase):
    def run_capture(self, root, *args, **kw):
        return run_script(SCRIPT, *args, "--date", DATE, "--vault", root, **kw)

    def test_stdin_capture_then_duplicate_exit_5(self):
        with temp_vault() as root:
            text = "# Grandma's Chai\n\nBoil water with ginger."
            r = self.run_capture(root, "https://example.com/chai", "--stdin", "--via", "web-fetch", stdin=text)
            self.assertEqual(r.returncode, 0, r.stderr)
            path = root / "raw" / f"{DATE}-grandmas-chai.md"
            meta = capture_meta(path)
            self.assertEqual((meta["title"], meta["kind"], meta["url"], meta["via"]),
                             ("Grandma's Chai", "website", "https://example.com/chai", "web-fetch"))
            self.assertIn("Boil water with ginger.", path.read_text(encoding="utf-8"))
            # same URL (trailing slash + fragment) is detected before any fetch
            r = self.run_capture(root, "https://example.com/chai/#step-2", "--json")
            self.assertEqual(r.returncode, 5)
            self.assertEqual(json.loads(r.stdout)["code"], 5)

    def test_duplicate_url_from_existing_raw_file(self):
        with temp_vault() as root:
            (root / "raw").mkdir()
            (root / "raw" / "2026-01-01-old.md").write_text(
                '---\ntitle: "Old"\nurl: "https://example.com/dal"\n---\nbody\n', encoding="utf-8")
            r = self.run_capture(root, "https://example.com/dal")
            self.assertEqual(r.returncode, 5)
            self.assertIn("2026-01-01-old.md", r.stderr)

    def test_stdin_without_text_is_usage_error(self):
        with temp_vault() as root:
            self.assertEqual(self.run_capture(root, "-", "--stdin", stdin="  \n").returncode, 1)

    def test_instagram_needs_stdin(self):
        with temp_vault() as root:
            url = "https://www.instagram.com/p/abc123/"
            self.assertEqual(self.run_capture(root, url).returncode, 6)
            r = self.run_capture(root, url, "--stdin", "--json", stdin="Crispy tofu\n1 block tofu")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["kind"], "instagram")

    def test_youtube_without_ytdlp_exit_3(self):
        with temp_vault() as root, tempfile.TemporaryDirectory() as empty_bin:
            r = self.run_capture(root, "https://www.youtube.com/watch?v=abc123", env={"PATH": empty_bin})
            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn("yt-dlp", r.stderr)

    def test_pdf_capture(self):
        pdf_bytes = (b"%PDF-1.4\n1 0 obj << /Type /Pages /Kids [2 0 R 3 0 R] /Count 2 >> endobj\n"
                     b"2 0 obj << /Type /Page >> endobj\n3 0 obj << /Type/Page >> endobj\n%%EOF\n")
        with temp_vault() as root:
            pdf = root.parent / "Family Cookbook.pdf"
            pdf.write_bytes(pdf_bytes)
            r = self.run_capture(root, pdf, "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual((out["kind"], out["companion"]), ("pdf", f"{DATE}-family-cookbook.pdf"))
            self.assertEqual((root / "raw" / out["companion"]).read_bytes(), pdf_bytes)
            meta = capture_meta(root / "raw" / f"{DATE}-family-cookbook.md")
            self.assertEqual((meta["pages"], meta["file"], meta["original_name"]),
                             (2, out["companion"], "Family Cookbook.pdf"))
            self.assertEqual(self.run_capture(root, pdf).returncode, 5)  # raw is immutable
            self.assertEqual(self.run_capture(root, pdf, "--force").returncode, 0)


if __name__ == "__main__":
    unittest.main()
