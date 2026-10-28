"""Pure-Python battle model: combatants, damage, the type chart and the end of a round.

No SQL runs here except reading the type chart once, and nothing here imports pygame.
That is what lets the same rules run in the window, in the terminal and in thousands of
simulated battles (design doc 5.8 and 9.1).

STATUS: step 1 done - combatants, damage, wards, exhaustion, round end, tested.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# Tuning constants (design doc 3.3 and 4.2). Change them here, never inline.
ROLL_LOW, ROLL_HIGH = 0.85, 1.00     # Pokemon-style damage spread
CRIT_CHANCE = 1 / 16
CRIT_MULT = 1.5
EXHAUSTED_MULT = 1.5                 # an overflowed caster is wide open (design doc 5.3)
VOID = "Void"                        # how a NULL element defends (design doc 4.2)
FOE_MP_REGEN = 5                     # foes.csv has no mp_regen column; same rate as Ada at level 1


@dataclass
class Combatant:
    """One side of the battle. The database mirrors these numbers so queries can read them."""
    name: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    mp_regen: int
    speed: int
    element: str | None
    weakness: str | None = None
    ward: int = 0
    # Set when an overflow drains the caster to 0 MP; the next enemy turn hits 1.5x.
    exhausted: bool = False
    # Keywords this combatant may write. The rune gate (magic/guard.py) reads this.
    runes: set[str] = field(default_factory=set)

    @property
    def hp_ratio(self) -> float:
        return self.hp / self.max_hp if self.max_hp else 0.0

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class BattleState:
    """Everything the brains are allowed to perceive (design doc 5.1)."""
    ada: Combatant
    foe: Combatant
    turn: int = 1                     # round number, starts at 1
    rng_seed: int = 0                 # written to query_log so any battle can be replayed
    foe_id: int = 1                   # which rows of foe_spells belong to this foe
    scries_used: int = 0              # free looks taken in the current turn
    foe_book: list[str] = field(default_factory=list)  # every query the foe has cast

    def side(self, who: str) -> Combatant:
        """'ada' or 'foe' -> the combatant. Callers pass the side, never the name."""
        return self.ada if who == "ada" else self.foe

    def other(self, who: str) -> Combatant:
        return self.foe if who == "ada" else self.ada

    def hp_ratio(self, who: str) -> float:
        return self.side(who).hp_ratio


@dataclass
class Hit:
    """The outcome of one damage roll, before it is applied to the target."""
    amount: int          # HP the target loses
    absorbed: int        # damage the ward soaked (and loses)
    multiplier: float    # type-chart multiplier, used for "super effective" messages
    crit: bool


def load_type_chart(conn) -> dict[tuple[str, str], float]:
    """Read the type chart once per battle; damage rolls then never touch SQL."""
    rows = conn.execute("SELECT attack, defend, multiplier FROM type_chart")
    return {(attack, defend): multiplier for attack, defend, multiplier in rows}


def effectiveness(element: str, target: Combatant, chart: dict) -> float:
    # A missing pair is neutral, so a new element never crashes a battle.
    return chart.get((element, target.element or VOID), 1.0)


def damage(power: int, element: str, target: Combatant, chart: dict,
           rng: random.Random) -> Hit:
    """Roll damage like design doc 4.2. Does not change the target: see apply_hit()."""
    multiplier = effectiveness(element, target, chart)
    # Always draw both numbers, so the rng sequence does not depend on the outcome.
    roll = rng.uniform(ROLL_LOW, ROLL_HIGH)
    crit = rng.random() < CRIT_CHANCE
    raw = power * multiplier * roll
    if crit:
        raw *= CRIT_MULT
    if target.exhausted:
        raw *= EXHAUSTED_MULT
    raw = round(raw)
    absorbed = min(raw, target.ward)          # the ward soaks flat damage first
    return Hit(amount=raw - absorbed, absorbed=absorbed, multiplier=multiplier, crit=crit)


def apply_hit(target: Combatant, hit: Hit) -> None:
    target.ward -= hit.absorbed
    target.hp = max(0, target.hp - hit.amount)


def heal(target: Combatant, amount: int) -> int:
    """Restore HP up to max_hp. Returns how much was actually restored."""
    before = target.hp
    target.hp = min(target.max_hp, target.hp + amount)
    return target.hp - before


def restore_mp(target: Combatant, amount: int) -> int:
    before = target.mp
    target.mp = min(target.max_mp, target.mp + amount)
    return target.mp - before


def add_ward(target: Combatant, amount: int) -> int:
    target.ward += amount
    return amount


def first_mover(state: BattleState, rng: random.Random) -> str:
    """The faster side acts first; a tie is a coin flip (design doc 4.1)."""
    if state.ada.speed != state.foe.speed:
        return "ada" if state.ada.speed > state.foe.speed else "foe"
    return rng.choice(["ada", "foe"])


def start_turn(state: BattleState, who: str) -> None:
    """Exhaustion lasts exactly one enemy turn: it wears off when the tired side acts again."""
    state.side(who).exhausted = False
    state.scries_used = 0


def winner(state: BattleState) -> str | None:
    # Ada falling counts first: hitting yourself with your own JOIN is still a loss.
    if not state.ada.alive:
        return "foe"
    if not state.foe.alive:
        return "ada"
    return None


def end_of_round(state: BattleState) -> str | None:
    """Regenerate MP, let wards decay, advance the round and report a winner if any."""
    for fighter in (state.ada, state.foe):
        fighter.mp = min(fighter.max_mp, fighter.mp + fighter.mp_regen)
        # Wards halve each round, so a ward is a short-term shield, not a permanent wall.
        fighter.ward //= 2
    state.turn += 1
    return winner(state)
