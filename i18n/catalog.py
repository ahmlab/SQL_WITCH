"""The text catalog: every player-visible string, looked up by key (rule 5 of CLAUDE.md).

    from i18n import t
    t("miscast.gibberish")                       # -> "Ada: Mmm that was NOT the right way..."
    t("world.summary.drop", table="spells")      # -> "you dropped spells"

Catalogs live in data/i18n/<locale>.json; English (en) is the source of truth. A key missing
from the current locale falls back to English; a key missing from English is returned as the key
itself and reported once, so a typo is visible on screen and in the log instead of crashing.

Message format: ICU MessageFormat (i18n/icu.py) for plurals and gender, so a line can say
"{count, plural, one {# row} other {# rows}}" and every language can follow its own CLDR rules.

Never imports pygame.

STATUS: catalogs, fallback to English, missing-key report, ICU formatting, locale switching.
"""

from __future__ import annotations

import json
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parent.parent / "data" / "i18n"
SOURCE = "en"


class Catalog:
    def __init__(self, folder: Path = CATALOG_DIR, locale: str = SOURCE):
        self.folder = Path(folder)
        self._cache: dict[str, dict[str, str]] = {}
        self.locale = locale
        self.missing: set[str] = set()
        self.listeners: list = []                      # called after a language switch

    def messages(self, locale: str) -> dict[str, str]:
        if locale not in self._cache:
            path = self.folder / f"{locale}.json"
            data = {}
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            # A catalog may group keys in nested objects; flatten them to dotted keys.
            self._cache[locale] = _flatten(data)
        return self._cache[locale]

    def set_locale(self, locale: str) -> None:
        self.locale = locale
        for listener in list(self.listeners):
            listener(locale)

    def reload(self) -> None:
        self._cache.clear()

    def has(self, key: str) -> bool:
        return key in self.messages(SOURCE)

    def raw(self, key: str, locale: str | None = None) -> str | None:
        locale = locale or self.locale
        text = self.messages(locale).get(key)
        if text is None and locale != SOURCE:
            text = self.messages(SOURCE).get(key)
        return text

    def t(self, key: str, **args) -> str:
        text = self.raw(key)
        if text is None:
            if key not in self.missing:
                self.missing.add(key)
                print(f"[i18n] missing key: {key}")
            return key
        from i18n.icu import format_message
        return format_message(text, args, self.locale)


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue                                   # "_help" notes for translators
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, full + "."))
        else:
            out[full] = value
    return out


CATALOG = Catalog()


def t(key: str, **args) -> str:
    """The text for `key` in the current language, with {placeholders} filled in."""
    return CATALOG.t(key, **args)


def set_locale(locale: str) -> None:
    CATALOG.set_locale(locale)


def locale() -> str:
    return CATALOG.locale
