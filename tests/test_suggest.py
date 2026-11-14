import datetime as dt
import unittest

from _helpers import FIXTURE_VAULT, SUGGEST_SCRIPTS, run_script, temp_vault

import kitchen_vault as kv
import suggest

SUGGEST = SUGGEST_SCRIPTS / "suggest.py"
LOG_MEAL = SUGGEST_SCRIPTS / "log_meal.py"
TODAY = dt.date(2026, 11, 14)


def pick(root=FIXTURE_VAULT, today=TODAY, cooldown=14, count=1, xc=(), xr=()):
    return suggest.suggest(root, today, cooldown, count, set(xc), set(xr))


class SuggestTests(unittest.TestCase):
    def test_oldest_cuisine_wins_ignoring_comments_and_future_meals(self):
        # italian last eaten 2026-10-01; the commented-out 11-10 and the future 12-25 entries
        # must not count, or italian would be newest / on cooldown.
        r = pick()
        self.assertEqual(r["suggestions"][0]["recipe"], "cacio-e-pepe")
        self.assertEqual(r["suggestions"][0]["cuisine_last_eaten"], "2026-10-01")
        self.assertEqual([c["cuisine"] for c in r["cuisine_ranking"]], ["italian", "indian", "mexican"])

    def test_never_eaten_recipe_first_within_cuisine(self):
        r = pick(count=2)
        self.assertEqual([s["recipe"] for s in r["suggestions"]], ["cacio-e-pepe", "dal-tadka"])
        self.assertEqual(r["suggestions"][1]["other_candidates_in_cuisine"], ["chana-masala"])

    def test_cooldown_excludes_recent(self):
        r = pick(cooldown=60)  # cutoff 2026-09-15: only never-eaten dal-tadka survives
        self.assertEqual([s["recipe"] for s in r["suggestions"]], ["dal-tadka"])

    def test_rotation_false_excluded(self):
        r = pick(count=10, cooldown=0)
        self.assertNotIn("holiday-biryani", [s["recipe"] for s in r["suggestions"]])
        with temp_vault(meals="") as root:
            r = pick(root, count=10, xc=["italian", "mexican"], xr=["dal-tadka", "chana-masala"])
            self.assertEqual(r["suggestions"], [])

    def test_deterministic(self):
        self.assertEqual(pick(count=3), pick(count=3))
        a = run_script(SUGGEST, "--vault", FIXTURE_VAULT, "--date", "2026-11-14", "--json")
        b = run_script(SUGGEST, "--vault", FIXTURE_VAULT, "--date", "2026-11-14", "--json")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(a.stdout, b.stdout)

    def test_tiebreak_rotates_between_iso_weeks(self):
        with temp_vault(meals="") as root:  # everything never eaten -> pure tie-break
            w46a = pick(root, today=dt.date(2026, 11, 9))["suggestions"][0]["cuisine"]
            w46b = pick(root, today=dt.date(2026, 11, 15))["suggestions"][0]["cuisine"]
            w47 = pick(root, today=dt.date(2026, 11, 16))["suggestions"][0]["cuisine"]
        self.assertEqual(w46a, w46b)  # stable within ISO week 46
        self.assertNotEqual(w46a, w47)

    def test_exit_2_when_nothing_eligible(self):
        args = ["--vault", FIXTURE_VAULT, "--date", "2026-11-14", "--cooldown-days", "60",
                "--exclude-recipe", "dal-tadka"]
        self.assertEqual(run_script(SUGGEST, *args).returncode, 2)
        self.assertEqual(run_script(SUGGEST, *args, "--json").returncode, 2)


class LogMealTests(unittest.TestCase):
    def test_appends_line(self):
        with temp_vault() as root:
            r = run_script(LOG_MEAL, "[[dal-tadka]]", "--date", "2026-11-14", "--note", "extra ghee",
                           "--vault", root)
            self.assertEqual(r.returncode, 0, r.stderr)
            text = (root / "meals.md").read_text(encoding="utf-8")
            self.assertTrue(text.endswith("\n- 2026-11-14 [[dal-tadka]] — extra ghee\n"))
            self.assertIn(("2026-11-14", "dal-tadka", "extra ghee"), kv.load_meals(root))

    def test_unknown_slug_rejected_unless_forced(self):
        with temp_vault() as root:
            before = (root / "meals.md").read_text(encoding="utf-8")
            r = run_script(LOG_MEAL, "dal", "--date", "2026-11-14", "--vault", root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("dal-tadka", r.stderr)  # did-you-mean
            self.assertEqual((root / "meals.md").read_text(encoding="utf-8"), before)
            r = run_script(LOG_MEAL, "dal", "--date", "2026-11-14", "--force", "--vault", root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((root / "meals.md").read_text(encoding="utf-8").endswith("- 2026-11-14 [[dal]]\n"))

    def test_creates_meals_file_via_env(self):
        with temp_vault() as root:
            (root / "meals.md").unlink()
            r = run_script(LOG_MEAL, "black-bean-tacos", "--date", "2026-11-01",
                           env={"KITCHEN_VAULT": str(root)})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(kv.load_meals(root), [("2026-11-01", "black-bean-tacos", "")])


if __name__ == "__main__":
    unittest.main()
