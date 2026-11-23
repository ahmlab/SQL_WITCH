"""The world after each query: snapshots, Rewind, the integrity check, reactions and tricks.

Freedom with consequences, and a way back (plan §4.1, pillar 3):
- Before every player query the battle database is snapshotted with SQLite's backup API (a
  full copy, schema included, about 0.1 ms at this size) together with a copy of the battle
  state. A snapshot that turns out to precede only a free look is discarded.
- After every query (player or foe) the world is fingerprinted, table by table, and compared:
  that gives the changes (a table dropped or emptied, rows added, columns renamed...).
- The integrity check classifies the world against what a battle needs (data/world.json):
  intact, altered (data changed), damaged (a needed table is gone, empty or unreadable, but the
  fight can go on) or broken (the engine cannot go on: the witch's or the foe's row is gone).
- Reactions (data/reactions.json) match those changes and say who speaks, which line (an i18n
  key) and what the world does about it; each has a cooldown in turns.
- Tricks (data/tricks.json) recognise a guardian broken with knowledge, and reward it.
- Rewind restores a snapshot, database and battle state, and drops the snapshots after it.

Why snapshots and not SAVEPOINTs: a savepoint lives inside a transaction the player could close
themselves (and rollback would undo the engine's own writes); a backup is a separate copy that
nothing in the player's SQL can touch, and it captures schema changes too. The backup API cannot
copy a database with an open transaction, which is why the guard closes any left open.

Never imports pygame. Never decides damage: magic/cast.py does.

STATUS: snapshots and rewind, fingerprints and changes, integrity, reactions, tricks.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from magic.db import DATA_DIR
from magic.rules import BattleState

INTEGRITY = ("intact", "altered", "damaged", "broken")       # from best to worst


def load(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Snapshot:
    """The world just before a player query, and what that query then did."""
    turn: int
    db: sqlite3.Connection
    state: BattleState
    summary_key: str = "world.summary.cast"
    summary_args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Change:
    table: str
    change: str


@dataclass(frozen=True)
class Reaction:
    id: str
    speaker: str                     # foe | grimoire | ada
    line_key: str
    effect: str
    args: tuple = ()                 # (name, value) pairs for the line
    page: str | None = None          # for codex_unlock

    @property
    def line_args(self) -> dict:
        return dict(self.args)


@dataclass
class Assessment:
    """What a query did to the world."""
    changes: list[Change]
    integrity: str
    missing: tuple[str, ...]
    reactions: list[Reaction]
    tricks: list[dict]
    refusal: Reaction | None = None
    duplicate: str | None = None     # a name now used twice across the tables


class World:
    def __init__(self, conn: sqlite3.Connection, state: BattleState,
                 rules: dict | None = None, reactions: dict | None = None,
                 tricks: dict | None = None):
        self.conn, self.state = conn, state
        self.rules = rules or load("world.json")
        self.reaction_rules = (reactions or load("reactions.json"))["reactions"]
        self.trick_rules = (tricks or load("tricks.json"))["tricks"]
        self.snapshots: list[Snapshot] = []
        self.fired: dict[str, int] = {}               # reaction id -> turn it last fired
        self.tricks_done: set[str] = set()
        self.baseline = self.fingerprint()
        self.last = self.baseline
        self.failing = self._failing()                # needs failing right now
        self.integrity, self.missing = "intact", ()

    # ------------------------------------------------------------ snapshots and rewind

    def snapshot(self, state: BattleState) -> Snapshot:
        db = sqlite3.connect(":memory:")
        self.conn.backup(db)
        snap = Snapshot(state.turn, db, copy.deepcopy(state))
        self.snapshots.append(snap)
        del self.snapshots[:-self.rules.get("snapshots_kept", 20)]
        return snap

    def discard(self, snap: Snapshot) -> None:
        if snap in self.snapshots:
            self.snapshots.remove(snap)
            snap.db.close()

    def restore(self, snap: Snapshot) -> BattleState:
        """Put the database back as it was in `snap`. Returns a copy of its battle state."""
        snap.db.backup(self.conn)
        self.last = self.fingerprint()
        self.failing = self._failing()
        self.integrity, self.missing = self._classify()
        return copy.deepcopy(snap.state)

    def rewind(self, index: int) -> tuple[Snapshot, BattleState]:
        """Rewind to snapshot `index` (0 is the oldest kept). Later snapshots are the future
        that no longer happened: they are dropped, and so is the one restored."""
        snap = self.snapshots[index]
        state = self.restore(snap)
        for later in self.snapshots[index:]:
            later.db.close()
        self.snapshots = self.snapshots[:index]
        return snap, state

    def entries(self) -> list[tuple[int, str, dict]]:
        """(turn, summary key, summary args) of every snapshot, oldest first, for the page."""
        return [(s.turn, s.summary_key, s.summary_args) for s in self.snapshots]

    # ------------------------------------------------------------ fingerprints

    def _objects(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()
        return {name.lower(): kind for name, kind in rows
                if name.lower() not in self.rules["ignore"] and not name.startswith("sqlite_")}

    def fingerprint(self) -> dict[str, tuple]:
        """Per table or view: (type, columns, row count, checksum of the non-volatile data)."""
        out = {}
        volatile = {t: set(c) for t, c in self.rules["volatile"].items()}
        for name, kind in self._objects().items():
            try:
                columns = tuple(r[1] for r in self.conn.execute(f'PRAGMA table_info("{name}")'))
                keep = [c for c in columns if c not in volatile.get(name, ())]
                if keep:
                    select = ", ".join(f'"{c}"' for c in keep)
                    rows = self.conn.execute(f'SELECT {select} FROM "{name}"').fetchall()
                else:
                    rows = []
                count = len(rows) if keep else self.conn.execute(
                    f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                digest = hashlib.sha1(repr(sorted(map(repr, rows))).encode()).hexdigest()
            except sqlite3.Error:                 # a view over a table that is gone
                columns, count, digest = (), -1, "broken"
            out[name] = (kind, columns, count, digest)
        return out

    @staticmethod
    def diff(before: dict, after: dict) -> list[Change]:
        changes = []
        for name in sorted(set(before) | set(after)):
            if name not in after:
                changes.append(Change(name, "dropped"))
            elif name not in before:
                changes.append(Change(name, "created"))
            else:
                (k0, c0, n0, d0), (k1, c1, n1, d1) = before[name], after[name]
                if k0 != k1 and k1 == "view":
                    changes.append(Change(name, "became_view"))
                if c0 != c1:
                    changes.append(Change(name, "columns_changed"))
                if n0 > 0 and n1 == 0:
                    changes.append(Change(name, "emptied"))
                elif n1 > n0:
                    changes.append(Change(name, "rows_added"))
                elif 0 <= n1 < n0:
                    changes.append(Change(name, "rows_removed"))
                elif d0 != d1 and c0 == c1:
                    changes.append(Change(name, "rows_changed"))
        return changes

    # ------------------------------------------------------------ integrity

    def _need_holds(self, need: dict) -> bool:
        params = {"ada": self.state.ada.name, "foe_id": self.state.foe_id}
        table = need["table"]
        try:
            if need["check"] == "table":
                return table in self._objects()
            if need["check"] == "rows":
                return self.conn.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() is not None
            if need["check"] == "row":
                where = need["where"]
                return self.conn.execute(f'SELECT 1 FROM "{table}" WHERE {where} LIMIT 1',
                                         params).fetchone() is not None
            if need["check"] == "readable":
                self.conn.execute(need["sql"], {k: v for k, v in params.items()
                                                if f":{k}" in need["sql"]}).fetchall()
                return True
        except sqlite3.Error:
            return False
        raise ValueError(f"unknown check {need['check']!r} in world.json")

    def _failing(self) -> list[dict]:
        return [need for need in self.rules["needs"] if not self._need_holds(need)]

    def _classify(self) -> tuple[str, tuple[str, ...]]:
        failing = self._failing()
        if failing:
            worst = max((n["missing"] for n in failing), key=INTEGRITY.index)
            return worst, tuple(sorted({n["table"] for n in failing}))
        changed = self.diff(self.baseline, self.fingerprint())
        return ("altered" if changed else "intact"), ()

    # ------------------------------------------------------------ after a query

    def assess(self, actor: str, statements=(), outcome=None, report=None,
               extra: tuple[str, ...] = ()) -> Assessment:
        """What the query that just ran did: changes, integrity, reactions, tricks."""
        now = self.fingerprint()
        changes = self.diff(self.last, now)
        failing = self._failing()
        newly = [n for n in failing if n not in self.failing]
        dropped = {c.table for c in changes if c.change == "dropped"}
        # A dropped table is also empty and unreadable; one reaction (to the drop) is enough.
        changes += [Change(n["table"], n["change"]) for n in newly if n["table"] not in dropped]
        for statement in statements:
            if statement.kind == "write" and statement.target:
                changes.append(Change(statement.target, statement.verb))
        if outcome is not None:
            if outcome.committed:
                changes.append(Change("*", "committed"))
            if outcome.rolled_back:
                changes.append(Change("*", "transaction_left_open"))
            if outcome.note:
                changes.append(Change("*", outcome.note))
        changes += [Change("*", name) for name in extra]
        self.last, self.failing = now, failing
        self.integrity, self.missing = self._classify()
        reactions = self._react(actor, changes)
        refusal = next((r for r in reactions if r.effect == "refuse"), None)
        duplicate = self.duplicate_name() if actor == "player" and statements and \
            any(s.kind in ("write", "schema") for s in statements) else None
        tricks = self._tricks(actor, report)
        return Assessment(changes, self.integrity, self.missing, reactions, tricks, refusal,
                          duplicate)

    def _react(self, actor: str, changes: list[Change]) -> list[Reaction]:
        out, turn = [], self.state.turn
        core = self.rules["core"]
        for rule in self.reaction_rules:
            when = rule["when"]
            if when.get("actor", "any") not in ("any", actor):
                continue
            for change in changes:
                if when["change"] != change.change:
                    continue
                if when["table"] not in ("*", change.table):
                    continue
                if when.get("like_core"):
                    like = next((c for c in core if change.table != c and
                                 re.sub(r"[^a-z]", "", change.table).startswith(c.rstrip("s"))),
                                None)
                    if like is None:
                        continue
                    args = (("table", like),)
                else:
                    args = (("table", change.table),)
                last, cooldown = self.fired.get(rule["id"]), rule.get("cooldown", 0)
                if cooldown and last is not None and turn - last < cooldown:
                    continue                      # it spoke too recently
                self.fired[rule["id"]] = turn
                out.append(Reaction(rule["id"], rule["speaker"], rule["line_key"], rule["effect"],
                                    args, rule.get("page")))
                break
        return out

    def duplicate_name(self) -> str | None:
        """A name used twice across the tables that hold names (checked in code, in character,
        never with a UNIQUE index on spells.name)."""
        parts = []
        objects = self._objects()
        for table in self.rules["names"]:
            if table in objects:
                columns = [r[1] for r in self.conn.execute(f'PRAGMA table_info("{table}")')]
                if "name" in columns:
                    parts.append(f'SELECT name FROM "{table}"')
        if not parts:
            return None
        sql = (f"SELECT name FROM ({' UNION ALL '.join(parts)}) WHERE name IS NOT NULL "
               "GROUP BY name HAVING COUNT(*) > 1 LIMIT 1")
        try:
            row = self.conn.execute(sql).fetchone()
        except sqlite3.Error:
            return None
        return row[0] if row else None

    # ------------------------------------------------------------ tricks

    def _tricks(self, actor: str, report) -> list[dict]:
        found = []
        for trick in self.trick_rules:
            if trick["id"] in self.tricks_done:
                continue
            recogniser = RECOGNISERS.get(trick["pattern"])
            if recogniser and recogniser(self, actor, report):
                self.tricks_done.add(trick["id"])
                found.append(trick)
        return found


def _foe_reads_player_view(world: World, actor: str, report) -> bool:
    """The foe cast from foe_spells while foe_spells was a view the player wrote."""
    if actor != "foe" or report is None or not report.rows:
        return False
    return world._objects().get("foe_spells") == "view"


def _player_reads_foe_query(world: World, actor: str, report) -> bool:
    """The player read the foe's own last query out of query_log."""
    if actor != "player" or report is None or not report.rows or not world.state.foe_book:
        return False
    last = world.state.foe_book[-1]
    return "query_log" in report.sql.lower() and any(last in map(str, row) for row in report.rows)


RECOGNISERS = {"foe_reads_player_view": _foe_reads_player_view,
               "player_reads_foe_query": _player_reads_foe_query}
