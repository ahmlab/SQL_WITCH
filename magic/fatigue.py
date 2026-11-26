"""Fatigue and Focus: rest as a mechanic (plan §4.5, prompt 08).

How it works: one meter from 0 (rested) to 1 (spent). Battle rounds, casts and the walk between
regions raise it; the Hearth lowers it (sleep resets it, a meal takes off a part, a letter a
little). The meter falls into bands (data/fatigue.json): each band sets how many rows the
Grimoire's page can show (4 -> 3 -> 2), how much the result text blurs, whether the Grimoire
yawns, and, in the top band, that the protagonist faints when the battle ends, whatever its
outcome, and wakes at the Hearth.

Focus is the reward for precision: a streak of efficient casts (spells landed, nothing lost past
the page, nothing fizzled) charges a short-lived bonus that adds a page row to the next casts.
Any sloppy cast (an overflow, a fizzle, a miscast) breaks the streak and spends the charges.
Free looks and pure writes neither build nor break it. Nothing here rewards speed.

Must not: never import pygame; never read the clock; never consume the battle rng. Every number
lives in data/fatigue.json.

STATUS: meter, bands, page rows, Focus streak and charges, rest actions, save round trip.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from magic.db import DATA_DIR


def load_tuning(path=DATA_DIR / "fatigue.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


TUNING = load_tuning()


@dataclass(frozen=True)
class Band:
    id: str
    below: float
    rows: int
    blur: float
    yawn: bool
    faint: bool


BANDS = [Band(b["id"], b["below"], b["rows"], b["blur"], b["yawn"], b["faint"])
         for b in TUNING["bands"]]


def band_of(value: float, bands=BANDS) -> Band:
    for band in bands:
        if value < band.below:
            return band
    return bands[-1]


@dataclass
class Fatigue:
    """The meter and the Focus streak. One per run: the Game keeps it, battles borrow it."""
    value: float = 0.0
    streak: int = 0                   # efficient casts in a row
    charges: int = 0                  # casts that still get the Focus row
    tuning: dict = field(default_factory=lambda: TUNING, repr=False, compare=False)

    # ------------------------------------------------------------ the meter

    @property
    def band(self) -> Band:
        return band_of(self.value)

    @property
    def focused(self) -> bool:
        return self.charges > 0

    def page_rows(self) -> int:
        """How many rows the page shows right now: the band's rows, plus Focus."""
        bonus = self.tuning["focus"]["bonus_rows"] if self.focused else 0
        return self.band.rows + bonus

    def rise(self, reason: str, times: int = 1) -> float:
        """Tire: `reason` is a key of rise in data/fatigue.json (round, cast, region...)."""
        before = self.value
        self.value = round(min(1.0, self.value + self.tuning["rise"][reason] * times), 4)
        return self.value - before

    def rest(self, kind: str) -> float:
        """Rest at the Hearth: sleep, meal or letter. Returns how much the meter fell."""
        before = self.value
        self.value = round(max(0.0, self.value - self.tuning["fall"][kind]), 4)
        if kind == "letter":
            # A letter from home steadies the hand: a Focus charge for the next fight.
            self.charges = max(self.charges, self.tuning["focus"]["letter_charges"])
        if kind == "sleep":
            self.streak = 0
        return before - self.value

    @property
    def faints(self) -> bool:
        return self.band.faint

    # ------------------------------------------------------------ Focus

    @staticmethod
    def judge(report) -> str:
        """'clean', 'sloppy' or 'neutral' for one cast report (or a miscast: report None)."""
        if report is None:
            return "sloppy"
        if report.overflow or report.fizzles:
            return "sloppy"
        if report.casts:
            return "clean"
        return "neutral"              # a free look, a write, a rewind

    def note(self, report) -> str:
        """Count one of the player's casts. Call it after the cast has been resolved with the
        rows of page_rows() (the charge it used is spent here)."""
        verdict = self.judge(report)
        if verdict == "neutral":
            return verdict
        if self.charges and verdict == "clean":
            self.charges -= 1
        if verdict == "sloppy":
            self.streak, self.charges = 0, 0
            return verdict
        self.streak += 1
        focus = self.tuning["focus"]
        if self.streak >= focus["streak"]:
            self.charges = focus["lasts_casts"]
            self.streak = 0
        return verdict

    # ------------------------------------------------------------ the save

    def to_dict(self) -> dict:
        return {"value": self.value, "streak": self.streak, "charges": self.charges}

    @classmethod
    def from_save(cls, value, focus: dict | None = None) -> "Fatigue":
        focus = focus or {}
        return cls(float(value or 0.0), int(focus.get("streak", 0)),
                   int(focus.get("charges", 0)))
