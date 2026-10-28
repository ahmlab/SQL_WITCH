"""The Asterisk Slime's brain: a probabilistic finite state machine (design doc 5.3).

Technique: a finite state machine whose transitions are sampled from probabilities instead of
being fixed. See Millington, "AI for Games", 3rd ed., chapter 5 (decision making: state
machines). It is the simplest brain in the game on purpose, so it is also a baseline.
Never imports pygame.

STATUS: step 3 done - Slime FSM with the HP < 30% override, tested.
"""

from __future__ import annotations

import random

from ai.base import Intent
from magic.rules import BattleState

# Each state lists (next state, probability). The rng picks one; nothing is hard-wired.
TRANSITIONS: dict[str, list[tuple[str, float]]] = {
    "wobble":    [("overcast", 0.7), ("wobble", 0.3)],
    "overcast":  [("exhausted", 1.0)],                 # its own overflow drains its MP
    "exhausted": [("careful", 0.5), ("wobble", 0.5)],
    "careful":   [("wobble", 1.0)],                    # casts SELECT * ... LIMIT 2
}
DESPERATE_HP = 0.3                                     # below this, always careful

# What the Slime wants to do in each state. ai/styles.py turns these into SQL.
SLIME_INTENTS: dict[str, Intent] = {
    "wobble":    Intent("wobble", None, "scry"),               # look at itself, regain MP
    "overcast":  Intent("overcast", "Ada", "attack"),          # the whole book at once
    "exhausted": Intent("exhausted", None, "scry"),            # too tired: stare and pant
    "careful":   Intent("careful", "Ada", "attack", {"limit": 2}),
}


def slime_legal_intents(state: BattleState) -> list[Intent]:
    """Everything the Slime may ever do. RandomBrain samples uniformly from this list."""
    return list(SLIME_INTENTS.values())


class SlimeBrain:
    """Probabilistic FSM. The current state is the brain's only memory."""

    def __init__(self, start: str = "wobble"):
        self.state = start
        self._last: dict = {}

    def decide(self, state: BattleState, rng: random.Random) -> Intent:
        previous = self.state
        me = state.foe
        if me.hp < DESPERATE_HP * me.max_hp:
            # Desperation overrides the dice: a cornered slime always reaches for LIMIT.
            self.state, probabilities, override = "careful", {"careful": 1.0}, True
        else:
            options = TRANSITIONS[previous]
            states, weights = zip(*options)
            self.state = rng.choices(states, weights)[0]
            probabilities, override = dict(options), False
        self._last = {"technique": "probabilistic FSM (Millington, AI for Games, ch. 5)",
                      "previous": previous, "state": self.state,
                      "probabilities": probabilities, "override": override,
                      "hp_ratio": round(me.hp_ratio, 2)}
        return SLIME_INTENTS[self.state]

    def explain(self) -> dict:
        return dict(self._last)
