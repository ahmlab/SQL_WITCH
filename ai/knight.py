"""Sir Wherewell, Knight of the Filter: a goal-driven guardian (design doc 5.4).

Mechanic: his Ward of Relevance turns aside every spell that is not super-effective against
him (magic/rules.py), and the first one that lands shatters it. His casts are always precise
WHERE filters, so his first query is the Invitation that teaches WHERE.

Techniques, all rule-based (no learning):
- Perception (ai/perception.py): he sees both sides' HP, MP and wards, knows which of his
  spells he can afford, and remembers Ada's casts: how much she hurts him (threat) and
  whether she has found his weakness (it fades if she stops using it).
- Stance, a state machine written as a `match` statement: vigilant, pressing, besieged,
  desperate, winded. It colours his priorities, like a knight's temperament.
- Goal-driven behaviour (Buckland, "Programming Game AI by Example", ch. 9): Think scores six
  strategic goals from the Percept and his stance and runs the winner as a multi-turn plan:
      execute       finish a weakened Ada with Verdict of the Deep
      restore_ward  fall back and raise the Ward of Relevance again
      strip_ward    close in, dispel Ada's ward, then strike
      press         close in and strike twice (heavy if he can afford it)
      hold_line     return to his post and raise Shield Wall
      catch_breath  pace at his post and rest (regain MP)
  A plan that becomes impossible (MP spent, ward shattered...) fails and he replans.
- Steering (ai/steering.py): he charges to the striking spot to attack, pursues a fleeing
  Ada to finish her, and walks back to his post to guard or recover.
Never imports pygame.

STATUS: perception, stance switch, six goal plans, steering orders.
"""

from __future__ import annotations

import random

from ai.base import Intent
from ai.goals import AtomicGoal, CompositeGoal, Evaluator, Goal
from ai.guardian import GuardianBrain
from ai.perception import Percept
from ai.steering import Movement

# Each action casts exactly one of his spells (data/foe_spells.csv, foe_id 2).
ACTION_SPELLS = {
    "strike": "Tidal Edge", "heavy": "Undertow Thrust", "finisher": "Verdict of the Deep",
    "relevance": "Ward of Relevance", "guard": "Shield Wall", "dispel": "Dispelling Cut",
}
DEFAULT_COSTS = {"strike": 4, "heavy": 7, "finisher": 12, "relevance": 6, "guard": 5,
                 "dispel": 4}
KNIGHT_INTENTS = {
    "strike": Intent("strike", "Ada", "attack"),
    "heavy": Intent("heavy", "Ada", "attack"),
    "finisher": Intent("finisher", "Ada", "attack"),
    "relevance": Intent("relevance", None, "relevance"),
    "guard": Intent("guard", None, "ward"),
    "dispel": Intent("dispel", "Ada", "dispel"),
    "rest": Intent("rest", None, "scry"),
}
FINISH_BELOW = 0.35            # Ada's HP ratio under which he goes for the kill
DESPERATE_BELOW = 0.3          # his own HP ratio under which he is desperate


def knight_legal_intents(state) -> list[Intent]:
    return list(KNIGHT_INTENTS.values())


# ------------------------------------------------------------------ desirabilities

STANCE_BIAS = {   # how each stance colours each goal (1.0 = neutral)
    "vigilant":  {"restore_ward": 1.0, "press": 1.0, "hold_line": 1.0},
    "pressing":  {"press": 1.3, "execute": 1.2, "hold_line": 0.7},
    "besieged":  {"restore_ward": 0.7, "hold_line": 1.5, "press": 1.2},
    "desperate": {"execute": 1.3, "press": 1.2, "restore_ward": 0.7, "hold_line": 0.6},
    "winded":    {"catch_breath": 2.0, "press": 0.6},
}


def _bias(goal: str, mode: str) -> float:
    return STANCE_BIAS.get(mode, {}).get(goal, 1.0)


def _execute(p: Percept, mode: str) -> float:
    if p.ada_hp_ratio >= FINISH_BELOW or not p.can("finisher"):
        return 0.0
    return 1.5 * _bias("execute", mode)


def _restore_ward(p: Percept, mode: str) -> float:
    if p.my_relevance or not p.can("relevance"):
        return 0.0
    # Perception: once Ada casts at his weakness, the ward stops her less (super-effective
    # spells pass anyway), so it is worth less than a Shield Wall or a counter-attack.
    return 1.3 * (1 - 0.8 * p.weakness_known) * _bias("restore_ward", mode)


def _strip_ward(p: Percept, mode: str) -> float:
    if p.ada_ward < 8 or not p.can("dispel"):
        return 0.0
    return (0.8 + p.ada_ward / 40) * _bias("strip_ward", mode)


def _press(p: Percept, mode: str) -> float:
    if not p.can("strike"):
        return 0.0
    return (0.7 + 0.5 * (1 - p.ada_hp_ratio)) * _bias("press", mode)


def _hold_line(p: Percept, mode: str) -> float:
    if not p.can("guard") or p.my_ward >= 5:
        return 0.0
    return (0.35 + 3 * p.threat) * _bias("hold_line", mode)


def _catch_breath(p: Percept, mode: str) -> float:
    return 0.15 * _bias("catch_breath", mode) + (0.6 if not p.can("strike") else 0.0)


# ------------------------------------------------------------------ plans

def _act(action: str, movement: Movement) -> AtomicGoal:
    return AtomicGoal(action, KNIGHT_INTENTS[action], movement,
                      requires=lambda p, a=action: a == "rest" or p.can(a))


def _move(name: str, behaviour: str, target: str) -> AtomicGoal:
    return AtomicGoal(name, movement=Movement(behaviour, target))


def _plan_execute(p: Percept) -> Goal:
    return CompositeGoal("execute", [_move("hunt", "pursue", "ada"),
                                     _act("finisher", Movement("pursue", "ada"))])


def _plan_restore_ward(p: Percept) -> Goal:
    return CompositeGoal("restore_ward", [_move("fall back", "arrive", "home"),
                                          _act("relevance", Movement("arrive", "home"))])


def _plan_strip_ward(p: Percept) -> Goal:
    return CompositeGoal("strip_ward", [_move("close in", "arrive", "front"),
                                        _act("dispel", Movement("arrive", "front")),
                                        _act("strike", Movement("arrive", "front"))])


def _plan_press(p: Percept) -> Goal:
    # Heavy first if he can pay for it and still strike next turn; otherwise two strikes.
    first = "heavy" if p.can_afford("heavy", "strike") else "strike"
    return CompositeGoal("press", [_move("charge", "arrive", "front"),
                                   _act(first, Movement("arrive", "front")),
                                   _act("strike", Movement("arrive", "front"))])


def _plan_hold_line(p: Percept) -> Goal:
    return CompositeGoal("hold_line", [_move("to post", "arrive", "home"),
                                       _act("guard", Movement("arrive", "home"))])


def _plan_catch_breath(p: Percept) -> Goal:
    return CompositeGoal("catch_breath", [_move("pace", "wander", "home"),
                                          _act("rest", Movement("wander", "home"))])


EVALUATORS = [
    Evaluator("execute", _execute, _plan_execute),
    Evaluator("restore_ward", _restore_ward, _plan_restore_ward),
    Evaluator("strip_ward", _strip_ward, _plan_strip_ward),
    Evaluator("press", _press, _plan_press),
    Evaluator("hold_line", _hold_line, _plan_hold_line),
    Evaluator("catch_breath", _catch_breath, _plan_catch_breath),
]


class KnightBrain(GuardianBrain):
    technique = "goal-driven behaviour + stance switch (Buckland ch. 9)"
    start_mode = "vigilant"
    repeat_penalty = 0.55          # a knight varies his tactics

    def __init__(self, costs: dict[str, int] | None = None):
        super().__init__(costs or dict(DEFAULT_COSTS), EVALUATORS)

    def next_mode(self, p: Percept, rng: random.Random) -> str:
        """The stance machine. Order matters: the first matching case wins."""
        match self.mode:
            case _ if p.my_hp_ratio < DESPERATE_BELOW:
                return "desperate"                     # nothing left to lose
            case _ if not p.can("strike"):
                return "winded"                        # cannot even swing his blade
            case "winded" if p.my_mp < 12:
                return "winded"                        # wait until he can fight properly
            case "vigilant" | "winded" | "pressing" if p.weakness_known > 0.5:
                return "besieged"                      # she found his weakness
            case "vigilant" | "winded" if p.ada_hp_ratio < 0.6:
                return "pressing"                      # she is weakening: press on
            case "besieged" if p.weakness_known <= 0.3 and p.my_relevance:
                return "vigilant"                      # the ward is up and she stopped
            case "winded":
                return "vigilant"
            case mode:
                return mode

    def idle_movement(self) -> Movement:
        match self.mode:
            case "pressing" | "desperate":
                return Movement("arrive", "front")      # keeps the pressure on
            case "besieged":
                return Movement("evade", "ada")         # keeps his distance
            case _:
                return Movement("wander", "home")       # paces before his gate
