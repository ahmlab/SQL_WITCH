"""The Spellbook: Scrolls, saved queries that are real SQL views (plan §4.4).

A query that has been cast successfully (at least one spell or item took effect) SCROLL_THRESHOLD
times may be saved as a Scroll. A Scroll is literally `CREATE VIEW scroll_<name> AS <query>` in
the battle database, so casting it is `SELECT * FROM scroll_<name>`, through guard.inspect and
cast.resolve like any other query, and the Codex page on CREATE VIEW explains that this is what
a view is. Scrolls belong to the player, not to one fight: the Spellbook keeps their text and
recreates the views in every battle database (and after a Rewind, which may predate them).

Parameters (a Scroll with {foe} in it) are a later step: see the skipped test.

Never imports pygame. Never bypasses the pipeline: a Scroll is only ever cast as a query.

STATUS: counting casts, saving, renaming, deleting, recreating views.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter

from magic import guard
from magic.db import DATA_DIR

with open(DATA_DIR / "spellbook.json", encoding="utf-8") as _f:
    _SETTINGS = json.load(_f)
SCROLL_THRESHOLD = _SETTINGS["threshold"]
MAX_NAME = _SETTINGS["max_name"]
NAME = re.compile(rf"^[A-Za-z][A-Za-z0-9_]{{0,{MAX_NAME - 1}}}$")
PREFIX = "scroll_"


class ScrollError(ValueError):
    """A Scroll cannot be saved, renamed or deleted; .key is the catalog line to show."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(key)


def normalise(sql: str) -> str:
    """The same query typed with different spacing or a final ; counts as the same query."""
    return " ".join(sql.strip().rstrip(";").split())


class Spellbook:
    def __init__(self, conn: sqlite3.Connection, scrolls: dict[str, str] | None = None):
        self.conn = conn
        self.scrolls: dict[str, str] = dict(scrolls or {})       # name -> query text
        self.casts: Counter[str] = Counter()
        self.ensure_views()

    @staticmethod
    def view(name: str) -> str:
        return f"{PREFIX}{name}"

    def ensure_views(self) -> None:
        """Every Scroll exists as a view in this database (after a battle starts or a Rewind)."""
        for name, sql in self.scrolls.items():
            self.conn.execute(f'CREATE VIEW IF NOT EXISTS "{self.view(name)}" AS {sql}')

    def note(self, sql: str, succeeded: bool) -> int:
        """Count a cast. Returns how many times this query has succeeded."""
        key = normalise(sql)
        if succeeded and not key.lower().startswith(f"select * from {PREFIX}"):
            self.casts[key] += 1
        return self.casts[key]

    def can_save(self, sql: str) -> bool:
        key = normalise(sql)
        return self.casts[key] >= SCROLL_THRESHOLD and key not in self.scrolls.values()

    def next_name(self) -> str:
        n = 1
        while f"scroll{n}" in self.scrolls:
            n += 1
        return f"scroll{n}"

    def save(self, sql: str, name: str | None = None) -> str:
        """Save a query as a Scroll. Returns the view to cast (scroll_<name>)."""
        name = name or self.next_name()
        if not NAME.match(name) or name in self.scrolls:
            raise ScrollError("ui.scroll.bad_name")
        signature = guard.inspect(sql)
        if signature.kind != "read":                  # a view can only hold a question
            raise ScrollError("ui.scroll.bad_name")
        query = normalise(sql)
        self.conn.execute(f'CREATE VIEW "{self.view(name)}" AS {query}')
        self.scrolls[name] = query
        return self.view(name)

    def rename(self, old: str, new: str) -> str:
        if old not in self.scrolls or not NAME.match(new) or new in self.scrolls:
            raise ScrollError("ui.scroll.bad_name")
        sql = self.scrolls.pop(old)
        self.conn.execute(f'DROP VIEW IF EXISTS "{self.view(old)}"')
        self.scrolls[new] = sql
        self.ensure_views()
        return self.view(new)

    def delete(self, name: str) -> None:
        if name not in self.scrolls:
            raise ScrollError("ui.scroll.bad_name")
        del self.scrolls[name]
        self.conn.execute(f'DROP VIEW IF EXISTS "{self.view(name)}"')

    @staticmethod
    def cast_sql(name: str) -> str:
        return f"SELECT * FROM {PREFIX}{name}"
