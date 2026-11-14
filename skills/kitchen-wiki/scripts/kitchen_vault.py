"""Shared helpers for the kitchen wiki vault. Standard library only.

Used by the kitchen-wiki, suggest-recipe and grocery-list skill scripts.

Frontmatter is parsed with a deliberately small YAML subset (see
references/schema.md, "Frontmatter rules"): top-level `key: value` scalars,
inline lists `[a, b]`, and block lists of scalars (`  - item`). Nested
mappings are rejected so every page stays readable in Obsidian's
Properties view and parseable without third-party packages.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

# folder under wiki/ -> page type
FOLDER_TYPES = {
    "recipes": "recipe",
    "ingredients": "ingredient",
    "equipment": "equipment",
    "techniques": "technique",
    "cuisines": "cuisine",
    "stores": "store",
    "sources": "source",
    "analyses": "analysis",
}

REQUIRED_FIELDS = {
    "recipe": ["title", "cuisine", "ingredients", "servings"],
    "ingredient": ["title", "category"],
    "equipment": ["title"],
    "technique": ["title"],
    "cuisine": ["title"],
    "store": ["title"],
    "source": ["title", "raw"],
    "analysis": ["title"],
}

INGREDIENT_CATEGORIES = [
    "produce", "herbs", "meat-seafood", "dairy-eggs", "bakery", "grains-pasta",
    "legumes", "canned-jarred", "spices", "condiments-sauces", "oils-vinegars",
    "baking", "nuts-seeds", "frozen", "beverages", "other",
]

WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
MEAL_LINE_RE = re.compile(r"^\s*[-*]\s+(\d{4}-\d{2}-\d{2})\b(.*)$")


class FrontmatterError(ValueError):
    pass


# --------------------------------------------------------------------------
# vault discovery
# --------------------------------------------------------------------------

def find_vault(explicit: str | None = None) -> Path:
    """Locate the Obsidian vault (the directory that contains wiki/)."""
    if explicit:
        vault = Path(explicit).expanduser()
    elif os.environ.get("KITCHEN_VAULT"):
        vault = Path(os.environ["KITCHEN_VAULT"]).expanduser()
    else:
        vault = None
        for d in [Path.cwd(), *Path.cwd().parents]:
            if (d / "mise" / "wiki").is_dir():
                vault = d / "mise"
                break
            if (d / "wiki").is_dir() and (d / ".obsidian").is_dir():
                vault = d
                break
        if vault is None:
            # scripts/ -> kitchen-wiki/ -> skills/ -> repo root
            vault = Path(__file__).resolve().parents[3] / "mise"
    if not (vault / "wiki").is_dir():
        sys.exit(f"error: no wiki/ directory in vault '{vault}'. "
                 "Pass --vault PATH or set KITCHEN_VAULT.")
    return vault.resolve()


# --------------------------------------------------------------------------
# frontmatter
# --------------------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---"):
        return None, text
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    raise FrontmatterError("frontmatter opened with --- but never closed")


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and (i == 0 or line[i - 1] in " \t[,:"):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def parse_scalar(s: str):
    s = s.strip()
    if s == "":
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        inner = s[1:-1]
        return re.sub(r'\\(["\\])', r"\1", inner) if s[0] == '"' else inner.replace("''", "'")
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _split_inline_list(s: str) -> list:
    items, buf, quote, depth = [], "", None, 0
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'" and not buf.strip():
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(buf)
            buf = ""
            continue
        buf += ch
    if buf.strip():
        items.append(buf)
    return [parse_scalar(x) for x in items]


def parse_frontmatter(fm: str) -> dict:
    data: dict = {}
    key = None
    for n, raw in enumerate(fm.split("\n"), 1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped == "-" or stripped.startswith("- "):
            if key is None or not isinstance(data.get(key), list):
                raise FrontmatterError(f"line {n}: list item without a list key: {raw!r}")
            data[key].append(parse_scalar(stripped[1:]))
            continue
        if line[0] in " \t":
            raise FrontmatterError(f"line {n}: nested mappings are not supported: {raw!r}")
        m = re.match(r"^([A-Za-z0-9_\-]+):(.*)$", line)
        if not m:
            raise FrontmatterError(f"line {n}: expected 'key: value': {raw!r}")
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            data[key] = []
        elif value.startswith("[") and value.endswith("]") and not value.startswith("[["):
            data[key] = _split_inline_list(value[1:-1])
        else:
            data[key] = parse_scalar(value)
    return data


# --------------------------------------------------------------------------
# pages and links
# --------------------------------------------------------------------------

def norm_slug(target: str) -> str:
    target = target.strip()
    if target.endswith(".md"):
        target = target[:-3]
    return target.rsplit("/", 1)[-1]


def links_in(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for v in value:
            out.extend(links_in(v))
        return out
    return [norm_slug(m.group(1)) for m in WIKILINK_RE.finditer(str(value))]


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


@dataclass
class Page:
    path: Path
    slug: str
    folder: str
    meta: dict
    body: str
    error: str | None = None

    @property
    def type(self) -> str | None:
        return self.meta.get("type") or FOLDER_TYPES.get(self.folder)

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.slug)

    def meta_links(self, *keys: str) -> list[str]:
        out = []
        for k in keys:
            out.extend(links_in(self.meta.get(k)))
        return out

    def all_links(self) -> set[str]:
        out = set(links_in(self.body))
        for v in self.meta.values():
            out.update(links_in(v))
        return out


@dataclass
class Vault:
    root: Path
    pages: dict[str, Page] = field(default_factory=dict)
    duplicates: dict[str, list[Path]] = field(default_factory=dict)

    @property
    def wiki(self) -> Path:
        return self.root / "wiki"

    def of_type(self, t: str) -> list[Page]:
        return sorted((p for p in self.pages.values() if p.type == t), key=lambda p: p.slug)

    def get(self, slug: str, t: str | None = None) -> Page | None:
        p = self.pages.get(norm_slug(slug))
        if p and t and p.type != t:
            return None
        return p


def load_page(path: Path, wiki_root: Path) -> Page:
    rel = path.relative_to(wiki_root)
    folder = rel.parts[0] if len(rel.parts) > 1 else ""
    text = path.read_text(encoding="utf-8")
    try:
        fm, body = split_frontmatter(text)
        meta = parse_frontmatter(fm) if fm is not None else {}
        return Page(path, path.stem, folder, meta, body)
    except FrontmatterError as e:
        return Page(path, path.stem, folder, {}, text, error=str(e))


def load_vault(root: Path) -> Vault:
    v = Vault(root)
    for path in sorted(v.wiki.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(v.wiki).parts):
            continue
        page = load_page(path, v.wiki)
        if page.slug in v.pages:
            v.duplicates.setdefault(page.slug, [v.pages[page.slug].path]).append(path)
            continue
        v.pages[page.slug] = page
    return v


def sha256_file(path: Path) -> str:
    """Hex sha256 of a file's bytes (used to stamp source pages' `raw_sha256`)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# ingredient lines and quantities
# --------------------------------------------------------------------------

UNICODE_FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4",
                     "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}

# base unit: teaspoon for volume, gram for weight
VOLUME_UNITS = {
    "tsp": 1, "teaspoon": 1, "tbsp": 3, "tablespoon": 3, "cup": 48, "c": 48,
    "fl oz": 6, "fluid ounce": 6, "pint": 96, "pt": 96, "quart": 192, "qt": 192,
    "ml": 0.2028841, "milliliter": 0.2028841, "l": 202.8841, "liter": 202.8841,
}
WEIGHT_UNITS = {
    "g": 1, "gram": 1, "kg": 1000, "kilogram": 1000,
    "oz": 28.3495, "ounce": 28.3495, "lb": 453.592, "pound": 453.592,
}
# preferred display order, largest first
VOLUME_DISPLAY = [("cup", 48), ("tbsp", 3), ("tsp", 1)]
WEIGHT_DISPLAY_US = [("lb", 453.592), ("oz", 28.3495)]
WEIGHT_DISPLAY_METRIC = [("kg", 1000), ("g", 1)]
SIZE_WORDS = {"small", "medium", "large", "big", "extra-large", "whole", "heaping", "scant"}


def singular(unit: str) -> str:
    u = unit.lower().strip().rstrip(".")
    if u in ("lbs",):
        return "lb"
    if u.endswith("ches") or u.endswith("shes") or u.endswith("oes"):
        return u[:-2]
    if u.endswith("s") and not u.endswith("ss") and len(u) > 2:
        return u[:-1]
    return u


def plural(unit: str) -> str:
    if unit.endswith(("ch", "sh", "s", "x")):
        return unit + "es"
    return unit + "s"


def _num(tok: str) -> Fraction | None:
    try:
        return Fraction(tok)
    except (ValueError, ZeroDivisionError):
        return None


def parse_amount(prefix: str) -> tuple[Fraction | None, str, bool]:
    """'1 1/2 cups' -> (3/2, 'cup', False). Third value: was it a range."""
    s = prefix.strip()
    for k, v in UNICODE_FRACTIONS.items():
        s = s.replace(k, f" {v}")
    s = re.sub(r"(\d)\s*[-–—]\s*(\d)", r"\1-\2", s)
    tokens = s.split()
    qty, i, ranged = None, 0, False
    while i < len(tokens):
        t = tokens[i]
        if "-" in t and all(_num(p) is not None for p in t.split("-") if p):
            parts = [_num(p) for p in t.split("-") if p]
            qty, ranged = (qty or 0) + max(parts), True
        elif (n := _num(t)) is not None:
            qty = (qty or 0) + n
        else:
            break
        i += 1
    unit_words = [w for w in tokens[i:] if w.lower() not in SIZE_WORDS]
    return qty, singular(" ".join(unit_words)), ranged


@dataclass
class IngredientUse:
    slug: str
    qty: Fraction | None
    unit: str
    note: str
    optional: bool
    ranged: bool
    raw: str


def parse_ingredient_line(line) -> IngredientUse | None:
    line = str(line)
    m = WIKILINK_RE.search(line)
    if not m:
        return None
    qty, unit, ranged = parse_amount(line[:m.start()])
    suffix = line[m.end():].strip()
    optional = "(optional)" in suffix.lower()
    note = re.sub(r"\(optional\)", "", suffix, flags=re.I).strip().lstrip(",;—–- ").strip()
    return IngredientUse(norm_slug(m.group(1)), qty, unit, note, optional, ranged, line)


def dimension(unit: str) -> str:
    if unit in VOLUME_UNITS:
        return "volume"
    if unit in WEIGHT_UNITS:
        return "weight"
    return "count:" + unit


def fmt_qty(x: Fraction | float) -> str:
    x = Fraction(x).limit_denominator(8)
    whole, rem = divmod(x.numerator, x.denominator)
    if rem == 0:
        return str(whole)
    frac = f"{rem}/{x.denominator}"
    return f"{whole} {frac}" if whole else frac


def fmt_amount(total: Fraction, dim: str, units_seen: set[str]) -> str:
    """Render a summed quantity. Keeps the original unit when only one was used."""
    if dim.startswith("count:"):
        unit = dim.split(":", 1)[1]
        if unit and total > 1:
            unit = plural(unit)
        return f"{fmt_qty(total)} {unit}".strip()
    if len(units_seen) == 1:
        unit = next(iter(units_seen))
        table = VOLUME_UNITS if dim == "volume" else WEIGHT_UNITS
        return f"{fmt_qty(total / Fraction(table[unit]).limit_denominator(10000))} {unit}"
    if dim == "volume":
        display = VOLUME_DISPLAY
    else:
        metric = any(u in ("g", "gram", "kg", "kilogram") for u in units_seen)
        display = WEIGHT_DISPLAY_METRIC if metric else WEIGHT_DISPLAY_US
    for unit, factor in display:
        if total >= Fraction(factor).limit_denominator(10000) * Fraction(1, 4) or unit == display[-1][0]:
            return f"{fmt_qty(total / Fraction(factor).limit_denominator(10000))} {unit}"
    return str(total)


def to_base(qty: Fraction, unit: str) -> Fraction:
    if unit in VOLUME_UNITS:
        return qty * Fraction(VOLUME_UNITS[unit]).limit_denominator(10000)
    if unit in WEIGHT_UNITS:
        return qty * Fraction(WEIGHT_UNITS[unit]).limit_denominator(10000)
    return qty


DEFAULT_YIELD_UNIT = "servings"


def parse_servings(value) -> Fraction | None:
    """A recipe's `servings` as an exact positive Fraction, or None if missing/invalid.

    Accepts frontmatter ints and decimals (4, 1.5). Strings, booleans, ranges
    and non-positive numbers are invalid.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        x = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None
    return x if x > 0 else None


def recipe_yield(page) -> tuple[Fraction | None, str]:
    """(servings, yield_unit) for a recipe page. yield_unit defaults to 'servings'."""
    unit = page.meta.get("yield_unit")
    unit = unit.strip() if isinstance(unit, str) and unit.strip() else DEFAULT_YIELD_UNIT
    return parse_servings(page.meta.get("servings")), unit


# --------------------------------------------------------------------------
# meal history
# --------------------------------------------------------------------------

def meals_path(vault: Path) -> Path:
    return vault / "meals.md"


def load_meals(vault: Path) -> list[tuple[str, str, str]]:
    """Return [(iso_date, recipe_slug, note)] from meals.md, in file order."""
    path = meals_path(vault)
    if not path.exists():
        return []
    out = []
    in_comment = False
    for line in path.read_text(encoding="utf-8").split("\n"):
        if "<!--" in line:
            in_comment = "-->" not in line
            continue
        if in_comment:
            in_comment = "-->" not in line
            continue
        m = MEAL_LINE_RE.match(line)
        if not m:
            continue
        date, rest = m.group(1), m.group(2)
        slugs = links_in(rest)
        note = WIKILINK_RE.sub("", rest).strip().lstrip("—–-:, ").strip()
        for slug in slugs:
            out.append((date, slug, note))
    return out
