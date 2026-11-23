"""The text catalog: every player-visible string, looked up by key (rule 5 of CLAUDE.md).

    from i18n import t
    t("miscast.gibberish")                       # -> "Ada: Mmm that was NOT the right way..."
    t("world.summary.drop", table="spells")      # -> "you dropped spells"

Catalogs live in data/i18n/<locale>.json; English (en) is the source of truth. A key missing
from the current locale falls back to English; a key missing from English is returned as the key
itself and reported once, so a typo is visible on screen and in the log instead of crashing.

Message format: ICU MessageFormat (i18n/icu.py) for plurals and gender, so a line can say
"{count, plural, one {# row} other {# rows}}" and every language can follow its own CLDR rules.

Every message also sees the player: {player.name} and {player.gender, select, feminine {...}
masculine {...} other {...}} (decision D3), from set_player(). The name is meant to stand alone
or in a fixed frame ("Ada:"), never where a language would decline it.

Languages are listed in data/i18n/locales.json. Each catalog keeps a "_status" object (key ->
draft | reviewed, written by tools/translate.py); menu_locales() lists the languages whose
reviewed share reaches the threshold, plus the ones in preview. The pseudo-locale qps is made
on the fly from English: accented and 35% longer, to catch text left in code and boxes that are
too small.

Never imports pygame.

STATUS: catalogs, fallback to English, missing-key report, ICU formatting, locale switching,
player name and gender, review status, the language menu, the qps pseudo-locale.
"""

from __future__ import annotations

import json
import weakref
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parent.parent / "data" / "i18n"
SOURCE = "en"


class Catalog:
    def __init__(self, folder: Path = CATALOG_DIR, locale: str = SOURCE):
        self.folder = Path(folder)
        self._cache: dict[str, dict[str, str]] = {}
        self._status: dict[str, dict[str, str]] = {}
        self.locale = locale
        self.missing: set[str] = set()
        self.listeners: list = []                      # called after a language switch
        self.player = {"name": "Ada", "gender": "feminine"}

    # ------------------------------------------------------------ the files

    def _load(self, locale: str) -> dict:
        path = self.folder / f"{locale}.json"
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def messages(self, locale: str) -> dict[str, str]:
        if locale not in self._cache:
            if locale == self.settings().get("pseudo", "qps"):
                from i18n.pseudo import pseudo
                self._cache[locale] = {k: pseudo(v) for k, v in self.messages(SOURCE).items()}
                return self._cache[locale]
            data = self._load(locale)
            self._status[locale] = dict(data.get("_status", {}))
            messages = {}
            if locale == SOURCE:
                # English also lives next to its content: scripts, guide.json, tutorial.json.
                from i18n.sources import all_sources
                messages.update(all_sources())
            # A catalog may group keys in nested objects; flatten them to dotted keys.
            messages.update(_flatten(data))
            self._cache[locale] = messages
        return self._cache[locale]

    def settings(self) -> dict:
        if "_settings" not in self._status:
            path = self.folder / "locales.json"
            self._status["_settings"] = json.loads(path.read_text(encoding="utf-8")) \
                if path.exists() else {"locales": {SOURCE: {"name": "English"}}}
        return self._status["_settings"]

    def status(self, locale: str) -> dict[str, str]:
        """key -> draft | reviewed, for the keys a locale has translated."""
        self.messages(locale)
        return self._status.get(locale, {})

    def reviewed_ratio(self, locale: str) -> float:
        if locale == SOURCE:
            return 1.0
        source = self.messages(SOURCE)
        status = self.status(locale)
        done = sum(1 for key in source if status.get(key) == "reviewed")
        return done / len(source) if source else 0.0

    def coverage(self, locale: str) -> float:
        """The share of English keys this locale has text for (draft or reviewed)."""
        source, own = self.messages(SOURCE), self.messages(locale)
        return sum(1 for key in source if key in own) / len(source) if source else 0.0

    def menu_locales(self, include_pseudo: bool = False) -> list[str]:
        """The languages a player may pick: reviewed enough, or in preview."""
        data = self.settings()
        out = []
        for code in data["locales"]:
            if code == data.get("pseudo"):
                if include_pseudo:
                    out.append(code)
                continue
            if code == SOURCE or code in data.get("preview", ()) or \
                    self.reviewed_ratio(code) >= data.get("review_threshold", 1.0):
                out.append(code)
        return out

    def is_draft(self, locale: str) -> bool:
        return locale != SOURCE and locale != self.settings().get("pseudo") and \
            self.reviewed_ratio(locale) < self.settings().get("review_threshold", 1.0)

    def name_of(self, locale: str) -> str:
        return self.settings()["locales"].get(locale, {}).get("name", locale)

    def script_of(self, locale: str) -> str:
        return self.settings()["locales"].get(locale, {}).get("script", "Latn")

    def set_player(self, name: str | None = None, gender: str | None = None) -> None:
        if name is not None:
            self.player["name"] = name
        if gender is not None:
            self.player["gender"] = gender

    def listen(self, callback) -> None:
        """Call back after every language switch. A bound method is held weakly, so a game
        that is thrown away stops listening by itself."""
        self.listeners.append(weakref.WeakMethod(callback) if hasattr(callback, "__self__")
                              else (lambda: callback))

    def set_locale(self, locale: str) -> None:
        self.locale = locale
        for ref in list(self.listeners):
            listener = ref()
            if listener is None:
                self.listeners.remove(ref)
            else:
                listener(locale)

    def reload(self) -> None:
        self._cache.clear()
        self._status.clear()

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
        return self.format(text, **args)

    def format(self, text: str, **args) -> str:
        """Fill a message (from the catalog or a script) with arguments and the player."""
        from i18n.icu import format_message
        return format_message(text, {"player": self.player, **args}, self.locale)


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


def set_player(name: str | None = None, gender: str | None = None) -> None:
    CATALOG.set_player(name, gender)
