"""Pressure: guardian moves that damage alone cannot answer (prompt 08 §3).

How it works: PressureBrain wraps a guardian's own brain. Most turns it simply asks that brain.
When the guardian's HP falls below the trigger in data/pressure.json it takes over for a move:
- big_turn: one turn reading its big spell's power (a free look the player can read in the
  guardian's book: the telegraph), then the big spell itself. A ward or a heal survives it.
- aegis: it raises an Aegis (a spell of kind 'aegis' in its book). While it stands every spell
  bounces off; items still work, and a cleansing item (Rust Salts) strips it.
The moves are Intents like any other; pressure_style() writes them as the SQL in the data, and
that SQL goes through the same pipeline as every query. The Intent is gone after Express.

Must not: never import pygame; never act without a query; never touch the rng (the wrapped
brain's rolls stay exactly as they were, so a fight keeps its seed).

STATUS: big_turn (telegraph, strike, repeat), aegis (and its strikes behind it); explain() for the F1 overlay.
"""

from __future__ import annotations

import json
import random

from ai.base import Intent
from magic.db import DATA_DIR
from magic.rules import BattleState


def load(path=DATA_DIR / "pressure.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


PRESSURE = load()

TELEGRAPH = Intent("pressure_telegraph", None, "scry")
STRIKE = Intent("pressure_strike", "Ada", "attack")
AEGIS = Intent("pressure_aegis", None, "ward")
DURING = Intent("pressure_during", "Ada", "attack")


class PressureBrain:
    def __init__(self, inner, spec: dict):
        self.inner = inner
        self.spec = spec
        self.pending = False          # telegraphed: the strike comes next turn
        self.fired_turn: int | None = None
        self._last: dict = {}

    def __getattr__(self, name):      # movement, mode, percept...: the wrapped brain's
        if name == "inner":
            raise AttributeError(name)
        return getattr(self.inner, name)

    def _due(self, state: BattleState) -> bool:
        # Never before its lesson: the guardian shows its technique first (the teaching
        # guarantee of its style), then it presses.
        if state.turn < self.spec.get("not_before_turn", 3):
            return False
        if state.foe.hp_ratio >= self.spec["trigger_hp"]:
            return False
        if self.fired_turn is None:
            return True
        every = self.spec.get("repeat_every", 0)
        return bool(every) and state.turn - self.fired_turn >= every

    def decide(self, state: BattleState, rng: random.Random) -> Intent:
        if state.foe_forgets or {"foe_spells", "enemies"} & set(state.missing):
            self.pending = False
            return self._inner(state, rng)
        if self.pending:
            self.pending = False
            return self._take(STRIKE, "strikes with its big spell")
        pressing = state.foe.aegis > 0 or (self.spec.get("press_after") and
                                           self.fired_turn is not None)
        if pressing and self.spec.get("during_sql") and state.foe.mp >= self.spec.get("during_mp", 0):
            # Behind its Aegis it does not need to guard: it presses its advantage.
            return self._take(DURING, "strikes from behind its Aegis")
        if self._due(state):
            self.fired_turn = state.turn
            if self.spec["kind"] == "big_turn":
                self.pending = True
                return self._take(TELEGRAPH, "gathers itself: the big spell is coming")
            return self._take(AEGIS, "raises its Aegis")
        return self._inner(state, rng)

    def _inner(self, state, rng) -> Intent:
        intent = self.inner.decide(state, rng)
        self._last = dict(self.inner.explain(), pressure="waiting")
        return intent

    def _take(self, intent: Intent, why: str) -> Intent:
        self._last = {"technique": getattr(self.inner, "technique", "?") + " + pressure",
                      "pressure": f"{self.spec['kind']}: {why}", "intent": intent.action}
        self.movement = getattr(self.inner, "idle_movement", lambda: None)()
        return intent

    def explain(self) -> dict:
        return dict(self._last)

    @property
    def telegraphed(self) -> bool:
        return self.pending


def pressure_style(spec: dict, style):
    """The guardian's SQL style, plus the pressure moves written from the data."""
    def render(intent: Intent, state: BattleState, turn: int) -> str:
        sql = {"pressure_telegraph": spec.get("telegraph_sql"),
               "pressure_strike": spec.get("strike_sql"),
               "pressure_aegis": spec.get("sql"),
               "pressure_during": spec.get("during_sql")}.get(intent.action)
        if sql:
            return sql.format(foe_id=state.foe_id)
        return style(intent, state, turn)
    return render
