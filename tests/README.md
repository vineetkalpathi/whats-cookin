# Tests

Standard-library `unittest` only. From the repo root:

```sh
python3 -m unittest discover -s tests          # everything
python3 -m unittest discover -s tests -p test_suggest.py   # one file
```

- `_helpers.py` puts the skill script dirs on `sys.path`, and provides `temp_vault()` (a
  throwaway copy of the fixture vault) and `run_script()` (runs a script with `sys.executable`
  for CLI and exit-code checks).
- `fixtures/vault/` is a tiny vault that follows `skills/kitchen-wiki/references/schema.md`:
  3 cuisines, 5 recipes (one with `rotation: false`), a dozen ingredients (staples and
  specialty items), one store with `stocked` / `not_stocked`, and a `meals.md` with a
  commented-out entry and a future-dated entry. Tests depend on its exact contents, so update
  the assertions when you change it.
- `fixtures/capture/recipe_page.html` is a saved page with schema.org Recipe JSON-LD. The tests
  never use the network.

Rules:
- **Never point tests at `mise/`.** Use the fixture vault.
- Tests that write (log_meal, capture, grocery `--out`) must work on a `temp_vault()` copy and
  pass `--vault` or `KITCHEN_VAULT`, never write into `tests/fixtures/`.
- Known bugs are recorded as `@unittest.expectedFailure` tests, with a comment. When the bug
  is fixed the test reports "unexpected success". Remove the decorator then.
