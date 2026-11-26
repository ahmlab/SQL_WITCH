"""The Hearth: rest, family and the party between regions (prompt 08 §2, plan pillar 5).

How it works: Hearth wraps the save (GameState) and the run's Fatigue, and offers the actions of
the camp: sleep (Fatigue resets), cook (a query over the recipes chooses the meal; a better
meal takes more Fatigue off), read a letter (letters arrive by story progress: one per region,
data/hearth/hearth.json), talk to a companion (a script node whose <<if>> lines read the story
variables and Fatigue), keep a named world backup (a SQL dump of the world database, for the
Chronomancer later), and leave. Leaving without sleeping is allowed: it tires the party a
little, it is counted, and the companions notice (Marta burns out after two in a row).

Every query here goes through the guard, in a fresh, hardened database: the Grimoire is never
bypassed, and the save only changes when a query succeeds.

Must not: never import pygame; never change the save on a refused query; never use the battle
rng (there is none here).

STATUS: sleep, cook by query, letters by story flag, companions, leaving, world backups.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from magic import guard
from magic.db import DATA_DIR, build_db, insert_rows, read_csv
from magic.fatigue import Fatigue
from magic.guard import Miscast

HEARTH_DIR = DATA_DIR / "hearth"


def load() -> dict:
    with open(HEARTH_DIR / "hearth.json", encoding="utf-8") as f:
        return json.load(f)


DATA = load()


@dataclass
class Meal:
    name: str
    rest: float
    columns: list[str]
    rows: list[tuple]


class Hearth:
    def __init__(self, state, fatigue: Fatigue, scrolls: dict[str, str] | None = None):
        self.state = state                  # save.state.GameState
        self.fatigue = fatigue
        self.scrolls = scrolls if scrolls is not None else dict(state.scrolls)
        story = state.story
        story.setdefault("letters_read", [])
        story.setdefault("skipped_sleeps", 0)
        story.setdefault("hearth_visits", 0)
        story.setdefault("burnout", False)
        self.slept = False
        self.ate = False

    @property
    def story(self) -> dict:
        return self.state.story

    def arrive(self) -> None:
        self.story["hearth_visits"] += 1
        self.slept = self.ate = False

    # ------------------------------------------------------------ resting

    def sleep(self) -> float:
        fell = self.fatigue.rest("sleep")
        self.slept = True
        self.story["skipped_sleeps"] = 0
        self.story["burnout"] = False            # a real night's rest heals the burnout
        return fell

    def leave(self) -> dict:
        """Leave the Hearth. Without sleep: a little more tired, and the party notices."""
        out = {"slept": self.slept, "burnout": False}
        if not self.slept:
            self.story["skipped_sleeps"] += 1
            self.fatigue.rise("skipped_sleep")
            rule = DATA["burnout"]
            if self.story["skipped_sleeps"] >= rule["skips"] and \
                    rule["companion"] in self.companions():
                self.story["burnout"] = out["burnout"] = True
        return out

    # ------------------------------------------------------------ the people

    def companions(self) -> list[str]:
        beaten = set(self.state.beaten)
        return [c["id"] for c in DATA["companions"] if c["joins_after"] in beaten]

    def companion(self, cid: str) -> dict:
        return next(c for c in DATA["companions"] if c["id"] == cid)

    def variables(self) -> dict:
        """What the Hearth's script conditions read (docs/WRITING.md)."""
        return {"fatigue": self.fatigue.value, "band": self.fatigue.band.id,
                "slept": self.slept, "ate": self.ate,
                "skipped_sleeps": self.story["skipped_sleeps"],
                "burnout": self.story["burnout"],
                "visits": self.story["hearth_visits"],
                "beaten": {k: True for k in self.state.beaten},
                "letters": len(self.story["letters_read"]),
                "story": dict(self.story)}

    # ------------------------------------------------------------ letters

    def letters_due(self) -> list[str]:
        """Letters that have arrived (their guardian is beaten) and are not read yet."""
        beaten = set(self.state.beaten)
        read = set(self.story["letters_read"])
        return [l["id"] for l in DATA["letters"] if l["after"] in beaten and l["id"] not in read]

    def read_letter(self, letter: str) -> float:
        if letter not in self.letters_due():
            raise ValueError(f"letter {letter!r} has not arrived")
        self.story["letters_read"].append(letter)
        return self.fatigue.rest("letter")

    # ------------------------------------------------------------ cooking

    def pantry(self) -> dict[str, int]:
        if "pantry" not in self.story:
            self.story["pantry"] = {r["name"]: r["qty"] for r in read_csv(HEARTH_DIR / "pantry.csv")}
        return self.story["pantry"]

    def kitchen(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.executescript("CREATE TABLE recipes (name TEXT, rest REAL, needs TEXT, serves INT);"
                           "CREATE TABLE pantry (name TEXT, qty INT);")
        insert_rows(conn, "recipes", read_csv(HEARTH_DIR / "recipes.csv"))
        insert_rows(conn, "pantry", [{"name": n, "qty": q} for n, q in self.pantry().items()])
        conn.commit()
        return guard.harden(conn)

    @staticmethod
    def cook_draft() -> str:
        return "SELECT name, rest FROM recipes\nWHERE needs = 'Oats'"

    def cook(self, sql: str) -> Meal:
        """A query over recipes (and the pantry) picks the meal: the first row whose name is a
        recipe the pantry can make. A look that names no recipe is just a look (rest 0)."""
        runes = guard.inspect(sql)
        if runes.kind != "read":
            raise Miscast("hearth.cook_read_only")
        conn = self.kitchen()
        columns, rows = guard.run_query(conn, sql)
        recipes = {r["name"]: r for r in read_csv(HEARTH_DIR / "recipes.csv")}
        pantry = self.pantry()
        for row in rows:
            for value in row:
                if value in recipes:
                    recipe = recipes[value]
                    if pantry.get(recipe["needs"], 0) <= 0:
                        raise Miscast("hearth.no_ingredient", meal=value, needs=recipe["needs"])
                    if self.ate:
                        raise Miscast("hearth.already_ate")
                    pantry[recipe["needs"]] -= 1
                    self.ate = True
                    fell = self.fatigue.rest("meal", recipe["rest"])
                    return Meal(value, fell, columns, rows)
        return Meal("", 0.0, columns, rows)

    # ------------------------------------------------------------ world backups

    def world(self) -> sqlite3.Connection:
        """The world database as the save holds it now: the witch, her satchel, her Scrolls."""
        level = 1 + len(self.state.beaten)
        conn = build_db(level=min(level, 7), inventory=self.state.inventory)
        for name, sql in self.scrolls.items():
            try:
                conn.execute(f'CREATE VIEW "scroll_{name}" AS {sql}')
            except sqlite3.Error:
                pass
        conn.commit()
        return conn

    def backup(self, name: str) -> str:
        """Save a named world backup (a SQL dump). The oldest goes when the shelf is full."""
        name = name.strip()[:24]
        if not name:
            raise ValueError("a backup needs a name")
        dump = "\n".join(self.world().iterdump())
        backups = self.state.backups
        backups.pop(name, None)
        backups[name] = dump
        while len(backups) > DATA["backups"]:
            backups.pop(next(iter(backups)))
        return name


def restore_backup(dump: str) -> sqlite3.Connection:
    """A world backup back as a live database (the Chronomancer's fight reads it)."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(dump)
    return conn
