"""The Codex: what the player has learned, written down (plan §4.2: runes become the Codex).

Runes used to be locks: a query with LIMIT miscast until the Slime taught it. Now nothing is
locked. guard.inspect() still returns a query's technique signature, and that signature feeds
the Codex: the first use of a technique, by the player or demonstrated by a guardian, unlocks
its page (exactly one page, once). A page holds the explanation and the SQLite vs PostgreSQL/
MySQL note (from the catalog), the guardian's example query and the player's own first query.

Guardians still demonstrate their technique. If the player already used it, the Invitation is
"acknowledged" instead of "taught", and the dialogue can branch on it (prompt 03).

Never imports pygame.

STATUS: pages from data/codex.json, unlock on first use, examples, acknowledgements, saving.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from i18n import t
from magic.db import DATA_DIR


@dataclass
class Page:
    id: str
    by: str                       # "player", a guardian's key, or "world" (backups, trickster)
    example: str | None = None    # the guardian's query that demonstrated it
    first_query: str | None = None   # the player's own first query with it
    turn_seen: int = 0

    @property
    def title(self) -> str:
        return t(f"codex.page.{self.id}.title")

    @property
    def text(self) -> str:
        return t(f"codex.page.{self.id}.text")

    @property
    def dialects(self) -> str:
        return t(f"codex.page.{self.id}.dialects")


class Codex:
    def __init__(self, order: list[str] | None = None):
        if order is None:
            with open(DATA_DIR / "codex.json", encoding="utf-8") as f:
                order = json.load(f)["order"]
        self.order = list(order)
        self.pages: dict[str, Page] = {}

    def knows(self, technique: str) -> bool:
        return technique in self.pages

    def record(self, technique: str, sql: str, turn: int = 0) -> bool:
        """The player used a technique. True if that unlocked its page (the first use)."""
        page = self.pages.get(technique)
        if page is not None:
            if page.first_query is None:
                page.first_query = sql             # the guardian showed it; now she wrote it
            return False
        self.pages[technique] = Page(technique, "player", first_query=sql, turn_seen=turn)
        return True

    def demonstrate(self, technique: str, sql: str, guardian: str, turn: int = 0) -> bool:
        """A guardian cast it. True if that unlocked the page."""
        page = self.pages.get(technique)
        if page is not None:
            if page.example is None:
                page.example = sql
            return False
        self.pages[technique] = Page(technique, guardian, example=sql, turn_seen=turn)
        return True

    def unlock(self, page_id: str, by: str = "world") -> bool:
        if page_id in self.pages:
            return False
        self.pages[page_id] = Page(page_id, by)
        return True

    def unlocked(self) -> list[Page]:
        rank = {name: i for i, name in enumerate(self.order)}
        return sorted(self.pages.values(), key=lambda p: rank.get(p.id, len(rank)))

    # ------------------------------------------------------------ saving (prompt 05)

    def to_json(self) -> list[dict]:
        return [asdict(page) for page in self.pages.values()]

    @classmethod
    def from_json(cls, data: list[dict]) -> "Codex":
        codex = cls()
        for page in data:
            codex.pages[page["id"]] = Page(**page)
        return codex
