"""The protagonist's name: the rules a name must pass before it enters the world (prompt 06).

The name becomes the `witch` row's name, so it lives in SQL: in queries, the log and Scrolls.
- 1 to 12 characters after trimming, any script (a Chinese name typed with an IME is fine);
- no quotes, backslashes or semicolons: they would break a string literal in a query;
- not the name of anything in the data files (a spell, an item, a guardian, a guardian's
  spell): names are unique across the world, or a spell would not know whom it hits;
- not an SQL keyword (SELECT, WHERE...), compared without case.
A refused name returns an i18n key (said in character) and a suggestion.

Never imports pygame.

STATUS: length, characters, data names, SQL keywords, suggestions.
"""

from __future__ import annotations

import csv
from functools import lru_cache

from magic.db import DATA_DIR

MAX_LENGTH = 12
FORBIDDEN = {"'", '"', "\\", ";", "`"}
SUGGESTIONS = ("Ada", "Grace", "Edgar", "Hedy", "Lin", "Mei", "Alan", "Rosa", "Kofi", "Iris")


@lru_cache(maxsize=1)
def data_names() -> frozenset[str]:
    """Every name in the data files, lower-cased."""
    names = set()
    for table in ("spells", "items", "foes", "foe_spells"):
        with open(DATA_DIR / f"{table}.csv", encoding="utf-8") as f:
            rows = (line for line in f if not line.startswith("#"))
            names |= {row["name"].strip().lower() for row in csv.DictReader(rows) if row.get("name")}
    return frozenset(names)


@lru_cache(maxsize=1)
def sql_keywords() -> frozenset[str]:
    from sqlglot.tokens import Tokenizer
    words = {k for k in Tokenizer.KEYWORDS if k.isalpha()}
    return frozenset(w.lower() for w in words | {"SELECT", "FROM", "WHERE", "TABLE", "NULL"})


def check_name(name: str) -> tuple[str | None, str]:
    """(None, the trimmed name) when it is fine, or (an i18n key, a suggestion)."""
    name = (name or "").strip()
    if not name:
        return "creator.name.empty", "Ada"
    if len(name) > MAX_LENGTH:
        return "creator.name.too_long", name[:MAX_LENGTH].strip()
    if FORBIDDEN & set(name):
        return "creator.name.characters", "".join(c for c in name if c not in FORBIDDEN) or "Ada"
    lowered = name.lower()
    if lowered in data_names():
        return "creator.name.taken", suggest(name)
    if lowered in sql_keywords():
        return "creator.name.keyword", suggest(name)
    return None, name


def suggest(name: str) -> str:
    """A free name close to the refused one: the same first letter if possible."""
    taken = data_names() | sql_keywords()
    same = [s for s in SUGGESTIONS if s[0].lower() == name[:1].lower() and s.lower() not in taken]
    free = [s for s in SUGGESTIONS if s.lower() not in taken]
    return (same or free or ["Ada"])[0]
