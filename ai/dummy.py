"""The Training Dummy: a guardian that does nothing, on purpose (the tutorial's partner).

It is a real foe row and takes real turns, so the tutorial runs on the same Battle as every
fight. Its "brain" always decides to stand still, and its style writes that as a real, harmless
look at itself. It owns no rows in foe_spells, so no query it could ever write can cast
anything: Ada is safe because of the data, not because of an `if`.
Never imports pygame.

STATUS: a brain that stands still and the look it writes.
"""

from __future__ import annotations

import random

from ai.base import Intent
from magic.rules import BattleState

STAND = Intent("stand", None, "scry")
DUMMY_LOOK = "SELECT name, hp FROM enemies"


class DummyBrain:
    """No perception, no goals, no randomness: it never touches the battle's rng."""

    def decide(self, state: BattleState, rng: random.Random) -> Intent:
        return STAND

    def explain(self) -> dict:
        return {"technique": "none: a training dummy", "intent": STAND.action}


def render_dummy(intent: Intent, state: BattleState, turn: int) -> str:
    return DUMMY_LOOK
