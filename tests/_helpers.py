"""Shared test helpers: script paths on sys.path, fixture vault copies, subprocess runner."""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KW_SCRIPTS = REPO / "skills" / "kitchen-wiki" / "scripts"
SUGGEST_SCRIPTS = REPO / "skills" / "suggest-recipe" / "scripts"
GROCERY_SCRIPTS = REPO / "skills" / "grocery-list" / "scripts"
FIXTURE_VAULT = Path(__file__).resolve().parent / "fixtures" / "vault"

for _d in (KW_SCRIPTS, SUGGEST_SCRIPTS, GROCERY_SCRIPTS):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))


@contextlib.contextmanager
def temp_vault(meals: str | None = None):
    """Copy the fixture vault into a temp dir (optionally replacing meals.md) and yield its path."""
    with tempfile.TemporaryDirectory(prefix="kitchen-test-") as tmp:
        vault = Path(tmp) / "vault"
        shutil.copytree(FIXTURE_VAULT, vault)
        if meals is not None:
            (vault / "meals.md").write_text(meals, encoding="utf-8")
        yield vault


def run_script(script: Path, *args, stdin: str | None = None, env: dict | None = None,
               cwd: Path | None = None) -> subprocess.CompletedProcess:
    full_env = {k: v for k, v in os.environ.items() if k != "KITCHEN_VAULT"}
    full_env.update(env or {})
    return subprocess.run([sys.executable, str(script), *map(str, args)], input=stdin,
                          capture_output=True, text=True, env=full_env, cwd=cwd, timeout=60)
