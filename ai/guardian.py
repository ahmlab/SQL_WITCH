"""The shape every guardian brain shares: perceive, change mode, think, act, move.

One turn of a GuardianBrain:
1. Perception turns the battle state into a Percept (ai/perception.py).
2. The mode (a small state machine written as a `match` statement in each guardian) reacts
   to what was perceived: e.g. the Knight becomes "besieged" once Ada finds his weakness.
3. Think arbitrates between strategic goals, whose desirability depends on the Percept and
   on the mode, and processes the chosen plan (ai/goals.py): this yields one Intent.
4. The plan also gives a Movement order, which the screen turns into steering
   (ai/steering.py).
ai/styles.py then writes the Intent as SQL, and the Intent is thrown away.
No machine learning anywhere: every decision is a rule a person can read in explain().
Never imports pygame.

STATUS: shared turn loop and explain() for the Slime and the Knight.
"""

from __future__ import annotations

import random

from ai.base import Intent
from ai.goals import Context, Evaluator, Think
from ai.perception import Perception, Percept, summary
from ai.steering import Movement
from magic.rules import BattleState

REST = Intent("rest", None, "scry")


class GuardianBrain:
    technique = "goal-driven guardian"
    start_mode = "idle"

    repeat_penalty = 1.0

    def __init__(self, costs: dict[str, int], evaluators: list[Evaluator]):
        self.perception = Perception(costs)
        self.think = Think(evaluators, self.repeat_penalty)
        self.mode = self.start_mode
        self.movement = Movement("hold")
        self.percept: Percept | None = None
        self._last: dict = {}

    # ------------------------------------------------------------ what each guardian defines

    def next_mode(self, p: Percept, rng: random.Random) -> str:
        """The state machine: a `match` on the current mode, guarded by the Percept."""
        return self.mode

    def mode_after(self, plan: str | None, mode: str) -> str:
        """The mode the guardian is in once it has acted (default: unchanged)."""
        return mode

    def idle_movement(self) -> Movement:
        """How it moves while it waits for its turn."""
        return Movement("wander", "home")

    def mode_details(self) -> dict:
        return {}

    # ------------------------------------------------------------ the turn

    def decide(self, state: BattleState, rng: random.Random) -> Intent:
        p = self.percept = self.perception.sense(state)
        previous = self.mode
        mode = self.next_mode(p, rng)
        ctx = Context(p, rng)
        intent = self.think.think(ctx, mode) or REST        # nothing possible: rest a turn
        self.mode = self.mode_after(self.think.current_name, mode)
        self.movement = ctx.movement or self.idle_movement()
        self._last = {
            "technique": self.technique,
            "mode": f"{previous} -> {self.mode}",
            **self.mode_details(),
            "sees": summary(p),
            "noticed": "; ".join(self.perception.log) or "nothing new",
            "goals": ", ".join(f"{k} {v:.2f}" for k, v in
                               sorted(self.think.scores.items(), key=lambda kv: -kv[1])),
            "plan": self.think.describe(),
            "steps": " / ".join(ctx.trace),
            "intent": intent.action,
            "movement": f"{self.movement.behaviour} {self.movement.target}",
        }
        return intent

    def explain(self) -> dict:
        return dict(self._last)
