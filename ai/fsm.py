"""The Asterisk Slime's brain: a probabilistic state machine driving simple goals (design doc 5.3).

Techniques, all rule-based (no learning):
- State machine: Millington, "AI for Games", 3rd ed., ch. 5. Its transitions are written as a
  `match` statement and sampled from probabilities with the battle's rng, so the Slime is
  unpredictable but reproducible by seed. Its mood (wobble, overcast, exhausted, careful)
  says what it feels like doing.
- Perception (ai/perception.py): it reads its own HP (below 30% it is desperate and always
  careful), its MP (no MP, no splat), and whether Ada is exhausted (then it pounces).
- Goal-driven behaviour (ai/goals.py): each mood favours one goal; Think arbitrates, and a
  goal that cannot be done (no MP) fails and is replaced, as in Buckland, ch. 9.
- Steering (ai/steering.py): it lunges at Ada to splat, creeps when careful, wobbles around
  its puddle while it waits.
It opens every battle with its classic mistake, SELECT * on its whole book, so the player's
first lesson is a query they can read and copy.
Never imports pygame.

STATUS: opening attack, match-based probabilistic FSM, perception, goals and steering.
"""

from __future__ import annotations

import random

from ai.base import Intent
from ai.goals import AtomicGoal, CompositeGoal, Evaluator, Goal
from ai.guardian import GuardianBrain
from ai.perception import Percept
from ai.steering import Movement
from magic.rules import BattleState

DESPERATE_HP = 0.3                                     # below this, always careful
MODES = ("opening", "wobble", "overcast", "exhausted", "careful")

# What the Slime wants to do in each mood. ai/styles.py turns these into SQL.
SLIME_INTENTS: dict[str, Intent] = {
    "wobble":    Intent("wobble", None, "scry"),               # look at itself, regain MP
    "overcast":  Intent("overcast", "Ada", "attack"),          # the whole book at once
    "exhausted": Intent("exhausted", None, "scry"),            # too tired: stare and pant
    "careful":   Intent("careful", "Ada", "attack", {"limit": 2}),
}


def transitions(mode: str) -> list[tuple[str, float]]:
    """The state machine (design doc 5.3), one case per mood: (next mood, probability)."""
    match mode:
        case "opening":
            return [("overcast", 1.0)]               # the first lesson: SELECT * on everything
        case "wobble":
            return [("overcast", 0.7), ("wobble", 0.3)]
        case "overcast":
            return [("exhausted", 1.0)]              # its own overflow drains its MP
        case "exhausted":
            return [("careful", 0.5), ("wobble", 0.5)]
        case "careful":
            return [("wobble", 1.0)]                 # casts SELECT * ... LIMIT 2
        case _:
            raise ValueError(f"unknown mood {mode!r}")


TRANSITIONS = {mode: transitions(mode) for mode in MODES}


def slime_legal_intents(state: BattleState) -> list[Intent]:
    """Everything the Slime may ever do. RandomBrain samples uniformly from this list."""
    return list(SLIME_INTENTS.values())


# ------------------------------------------------------------------ goals

def _mood_weight(goal_mood: str, mode: str) -> float:
    return 1.0 if goal_mood == mode else 0.05


def _splat(p: Percept, mode: str) -> float:
    if mode == "careful":
        return 0.0                                    # desperate slimes do not splat
    # Perception: Ada is wide open (1.5x damage). That beats wobbling even on the worst roll.
    pounce = 1.5 if p.ada_exhausted else 0.0
    return max(_mood_weight("overcast", mode), pounce)


def _plan_splat(p: Percept) -> Goal:
    return CompositeGoal("splat", [
        AtomicGoal("lunge", movement=Movement("seek", "front")),
        AtomicGoal("splat", SLIME_INTENTS["overcast"], Movement("seek", "front"),
                   requires=lambda q: q.can("splat")),
    ])


def _plan_careful(p: Percept) -> Goal:
    return CompositeGoal("careful", [
        AtomicGoal("creep", movement=Movement("arrive", "front")),
        AtomicGoal("careful", SLIME_INTENTS["careful"], Movement("arrive", "front"),
                   requires=lambda q: q.can("careful")),
    ])


EVALUATORS = [
    Evaluator("splat", _splat, _plan_splat),
    Evaluator("catch_breath", lambda p, m: _mood_weight("wobble", m),
              lambda p: AtomicGoal("catch_breath", SLIME_INTENTS["wobble"],
                                   Movement("wander", "home"))),
    Evaluator("pant", lambda p, m: _mood_weight("exhausted", m),
              lambda p: AtomicGoal("pant", SLIME_INTENTS["exhausted"],
                                   Movement("arrive", "home"))),
    Evaluator("careful", lambda p, m: _mood_weight("careful", m), _plan_careful),
]
PLAN_MOOD = {"splat": "overcast", "catch_breath": "wobble", "pant": "exhausted",
             "careful": "careful"}


class SlimeBrain(GuardianBrain):
    technique = "probabilistic FSM + goals (Millington ch. 5, Buckland ch. 9)"
    start_mode = "opening"

    def __init__(self, costs: dict[str, int] | None = None, start: str | None = None):
        # Splatting or being careful needs at least its cheapest spell (Goo Spit, 2 MP).
        super().__init__(costs or {"splat": 2, "careful": 2}, EVALUATORS)
        if start is not None:
            self.mode = start
        self._transition: dict = {}

    def next_mode(self, p: Percept, rng: random.Random) -> str:
        if p.my_hp_ratio < DESPERATE_HP:
            # Desperation overrides the dice: a cornered slime always reaches for LIMIT.
            self._transition = {"probabilities": {"careful": 1.0}, "override": True}
            return "careful"
        options = transitions(self.mode)
        moods, weights = zip(*options)
        self._transition = {"probabilities": dict(options), "override": False}
        return rng.choices(moods, weights)[0]

    def mode_after(self, plan: str | None, mode: str) -> str:
        # The machine follows what the Slime really did (e.g. it pounced instead of wobbling).
        return PLAN_MOOD.get(plan, mode)

    def idle_movement(self) -> Movement:
        match self.mode:
            case "wobble" | "opening":
                return Movement("wander", "home")     # wobble around its puddle
            case _:
                return Movement("arrive", "home")     # back to its puddle after acting

    def mode_details(self) -> dict:
        return dict(self._transition)

    @property
    def state(self) -> str:
        """The current mood (the name the first version of this brain used)."""
        return self.mode
