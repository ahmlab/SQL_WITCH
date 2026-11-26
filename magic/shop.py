"""The stall: buying is a query (prompt 08 §3). It teaches INSERT ... SELECT before Act 2.

How it works: each query runs in a fresh, hardened database built from the save: `items` (the
satchel, one row per item, no key: a second Ether is a second row), `stall` (what is for sale,
with prices, from data/hearth/stall.csv), `purse` (coins), and the name-holding tables of the
world (`spells`, `enemies`, `witch`), so a name stays unique across all of them. A read is a
look at the stall. A buy is an INSERT INTO items ... SELECT ... FROM stall; the shopkeeper then
checks every new row: it must be something on the stall (kind and amount as sold), its name
must not belong to a spell, a foe or the witch (checked in code, never by a UNIQUE index), and
the purse must cover price x qty. Then, and only then, the save's satchel and purse change.
Anything else (UPDATE, DELETE, DROP...) is refused in character. The shopkeeper drafts the
query with the player: draft() fills in the editor.

Must not: never import pygame; never change the save on a refused query; never bypass guard.

STATUS: look, buy by INSERT ... SELECT, checks, purse, shopkeeper's draft.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from magic import guard
from magic.db import DATA_DIR, insert_rows, read_csv
from magic.guard import Miscast

STALL = DATA_DIR / "hearth" / "stall.csv"
SCHEMA = """
CREATE TABLE items  (name TEXT, kind TEXT, amount INT, qty INT);
CREATE TABLE stall  (name TEXT, kind TEXT, amount INT, price INT);
CREATE TABLE purse  (coins INT);
CREATE TABLE spells (name TEXT, element TEXT, power INT, mp_cost INT, kind TEXT);
CREATE TABLE enemies (name TEXT);
CREATE TABLE witch  (name TEXT);
"""


def catalogue() -> dict[str, dict]:
    return {row["name"]: row for row in read_csv(DATA_DIR / "items.csv")}


def stall_rows() -> list[dict]:
    return read_csv(STALL)


@dataclass
class Receipt:
    columns: list[str]
    rows: list[tuple]
    bought: dict[str, int] = field(default_factory=dict)
    paid: int = 0
    kind: str = "read"


class Shop:
    def __init__(self, inventory: dict[str, int] | None, coins: int, witch: str = "Ada"):
        cat = catalogue()
        self.inventory = dict(inventory if inventory is not None else
                              {n: r["qty"] for n, r in cat.items() if r["qty"]})
        self.coins = int(coins)
        self.witch = witch

    def _db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        cat = catalogue()
        insert_rows(conn, "items", [{"name": n, "kind": cat[n]["kind"], "amount": cat[n]["amount"],
                                     "qty": q} for n, q in self.inventory.items()
                                    if q > 0 and n in cat])
        insert_rows(conn, "stall", stall_rows())
        conn.execute("INSERT INTO purse VALUES (?)", (self.coins,))
        insert_rows(conn, "spells", [{k: r[k] for k in ("name", "element", "power", "mp_cost",
                                                         "kind")}
                                     for r in read_csv(DATA_DIR / "spells.csv")])
        insert_rows(conn, "enemies", [{"name": r["name"]} for r in read_csv(DATA_DIR / "foes.csv")])
        conn.execute("INSERT INTO witch VALUES (?)", (self.witch,))
        conn.commit()
        return guard.harden(conn)

    @staticmethod
    def draft(item: str = "Healing Herb", qty: int = 1) -> str:
        """The shopkeeper's half of the query: the player completes or changes it."""
        return ("INSERT INTO items (name, kind, amount, qty)\n"
                f"SELECT name, kind, amount, {qty} FROM stall\nWHERE name = '{item}'")

    def query(self, sql: str) -> Receipt:
        """Run one query at the stall. Raises Miscast (nothing changes) when it is refused."""
        runes = guard.inspect(sql)
        statements = list(runes.statements)
        if runes.kind != "read" and not (len(statements) == 1 and statements[0].verb == "insert"
                                         and (statements[0].target or "").lower() == "items"):
            raise Miscast("shop.refuse")
        conn = self._db()
        before = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM items").fetchone()[0]
        columns, rows = guard.run_query(conn, sql)
        if runes.kind == "read":
            return Receipt(columns, rows)
        new = conn.execute("SELECT name, kind, amount, qty FROM items WHERE rowid > ?",
                           (before,)).fetchall()
        if not new:
            raise Miscast("shop.nothing")
        prices = {r["name"]: r for r in stall_rows()}
        taken = {r[0] for r in conn.execute(
            "SELECT name FROM spells UNION SELECT name FROM enemies UNION SELECT name FROM witch")}
        bought, paid = {}, 0
        for name, kind, amount, qty in new:
            if name in taken:
                raise Miscast("miscast.duplicate_name", name=name)
            sold = prices.get(name)
            if sold is None or kind != sold["kind"] or amount != sold["amount"]:
                raise Miscast("shop.not_for_sale", name=str(name))
            if not isinstance(qty, int) or qty < 1:
                raise Miscast("shop.bad_qty", name=name)
            bought[name] = bought.get(name, 0) + qty
            paid += sold["price"] * qty
        if paid > self.coins:
            raise Miscast("shop.too_poor", price=paid, coins=self.coins)
        self.coins -= paid
        for name, qty in bought.items():
            self.inventory[name] = self.inventory.get(name, 0) + qty
        return Receipt(["name", "qty"], sorted(bought.items()), bought, paid, "write")
