"""The shared vocabulary of every foe brain: intents, the Brain interface and the random baseline.

A brain decides WHAT to do as an Intent. A style (ai/styles.py) then writes that intent as
SQL, and after that the intent is thrown away: damage can only come from the executed query
(design doc 5.1, "why decide and express are separate"). Never imports pygame.

STATUS: step 3 done - Intent, Brain protocol, RandomBrain baseline.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Protocol

from magic.rules import BattleState


@dataclass(frozen=True)
class Intent:
    """A small, finite description of an action, e.g. Intent('overcast', 'Ada', 'attack')."""
    action: str                  # what the brain wants, in its own words
    target: str | None = None    # combatant name the intent is aimed at, if any
    kind: str = "attack"         # attack | heal | ward | scry
    params: dict = field(default_factory=dict, compare=True, hash=False)


class Brain(Protocol):
    """Every foe AI has this shape, so any brain can be paired with any style."""

    def decide(self, state: BattleState, rng: random.Random) -> Intent:
        ...

    def explain(self) -> dict:
        """The reasoning behind the last decision, for the F1 overlay and the report."""
        ...


class RandomBrain:
    """Uniform choice over the legal intents. The evaluation baseline (design doc section 9):
    any real brain should do measurably better than this."""

    def __init__(self, legal_intents: Callable[[BattleState], list[Intent]]):
        self.legal_intents = legal_intents
        self._last: dict = {}

    def decide(self, state: BattleState, rng: random.Random) -> Intent:
        options = self.legal_intents(state)
        choice = rng.choice(options)
        self._last = {"technique": "uniform random (baseline)",
                      "choices": [i.action for i in options],
                      "probability": 1 / len(options),
                      "picked": choice.action}
        return choice

    def explain(self) -> dict:
        return dict(self._last)
