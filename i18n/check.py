"""Checks on the catalogs: does every string fit its box, what is untranslated, which lines
need two gendered forms. Used by tools/i18n_report.py and tests/test_i18n.py.

Box sizes live in data/i18n/boxes.json (cells and lines per key pattern). A string is filled
with sample arguments, its inline markup removed, then wrapped exactly like the game wraps it.

Never imports pygame.

STATUS: overflow per box, untranslated report, gender counts, the English pronoun lint.
"""

from __future__ import annotations

import fnmatch
import json
import re
from functools import lru_cache

from i18n.catalog import CATALOG, CATALOG_DIR, SOURCE
from i18n.width import _pieces, text_cells, wrap

# English words that inflect for the protagonist's gender, here or in most target languages.
PRONOUNS = re.compile(r"\b(she|her|hers|herself|he|him|his|himself)\b", re.I)


@lru_cache(maxsize=1)
def boxes() -> dict:
    return json.loads((CATALOG_DIR / "boxes.json").read_text(encoding="utf-8"))


def box_of(key: str) -> tuple:
    for pattern, cells, lines in boxes()["boxes"]:
        if fnmatch.fnmatchcase(key, pattern):
            return cells, lines
    return 76, "scroll"


def rendered(key: str, text: str, locale: str) -> str:
    """The text as the player reads it: arguments filled, markup gone."""
    from i18n.icu import format_message
    from story.script import plain
    args = {"player": CATALOG.player, **boxes()["samples"]}
    shown = plain(format_message(text, args, locale))
    if key.startswith("grimoire."):                    # the status line squeezes its spaces
        for squeeze in ((" -> ", "->"), (" | ", "|")):
            shown = shown.replace(*squeeze)
    return shown


def overflow(key: str, text: str, locale: str) -> str | None:
    """Why `text` does not fit its box, or None."""
    cells, lines = box_of(key)
    if cells == "tutorial":
        return None                                    # magic/tutorial.py measures these
    shown = rendered(key, text, locale)
    if lines == "scroll":                              # only an unbreakable word can overflow
        long = [p for w in shown.split() for p in _pieces(w) if text_cells(p) > cells]
        return f"a word wider than the box ({cells} cells): {long[0]}" if long else None
    if lines == 1:
        return None if text_cells(shown) <= cells else \
            f"{text_cells(shown)} cells in a box of {cells}: {shown!r}"
    rows = wrap(shown, cells)
    return None if len(rows) <= lines else \
        f"{len(rows)} lines of {cells} cells in a box of {lines}: {shown!r}"


def overflows(locale: str) -> list[str]:
    source = CATALOG.messages(SOURCE)
    own = CATALOG.messages(locale)
    out = []
    for key in source:
        text = own.get(key, source[key])
        if (why := overflow(key, text, locale)):
            out.append(f"{key}: {why}")
    if locale != CATALOG.settings().get("pseudo"):
        out += tutorial_overflows(locale)
    return out


def tutorial_overflows(locale: str) -> list[str]:
    """The tutorial measures its own boxes (magic/tutorial.py): in this language."""
    from i18n.catalog import set_locale
    from magic.tutorial import load_script, script_problems
    before = CATALOG.locale
    try:
        set_locale(locale)
        return [f"tutorial {p}" for p in script_problems(load_script())]
    finally:
        set_locale(before)


def untranslated(locale: str) -> list[str]:
    own = CATALOG.messages(locale)
    return [key for key in CATALOG.messages(SOURCE) if key not in own]


def gendered(locale: str) -> int:
    """Entries of a language that carry two forms for the protagonist's gender."""
    return sum(1 for text in CATALOG.messages(locale).values() if "player.gender" in text)


def pronoun_warnings() -> list[str]:
    """English lines with he/she/his/her and no gender select. Most are about someone else
    (the Knight's blade); a writer checks each one, the lint only points at them."""
    return [f"{key}: {text}" for key, text in CATALOG.messages(SOURCE).items()
            if PRONOUNS.search(re.sub(r"\{player\.gender[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", text))
            and "player.gender" not in text]


def report() -> str:
    lines = []
    for code in CATALOG.settings()["locales"]:
        if code in (SOURCE, CATALOG.settings().get("pseudo")):
            continue
        cover = CATALOG.coverage(code)
        if cover == 0:
            lines.append(f"{code:8} not started")
            continue
        lines.append(f"{code:8} {cover:6.1%} translated  {CATALOG.reviewed_ratio(code):6.1%} "
                     f"reviewed  {len(untranslated(code)):3} missing  {gendered(code):3} with "
                     f"two gendered forms")
    return "\n".join(lines)
