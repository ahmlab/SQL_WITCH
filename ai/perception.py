"""Perception: what a guardian senses each turn, and what it remembers (design doc 5.1, "Perceive").

A brain never reads the battle state directly. Its Perception turns the state into a Percept:
a small, read-only summary built from three senses:
- sight: HP, MP, wards and statuses on both sides, as the tables show them;
- its own book: which of its spells it can afford right now;
- memory: Ada's past casts (BattleState.ada_casts), from which it estimates how dangerous she
  is (threat), whether she has found its weakness, and how she likes to cast.
Memory fades: a weakness Ada has not used for a few turns is half forgotten. Everything is
plain arithmetic on the state, with no learning and no hidden information (it never sees
Ada's next query, only what she already did, exactly like the player sees the foe's book).
Technique: Millington, "AI for Games", 3rd ed., ch. 11 (world interfacing and sense
management); Buckland, "Programming Game AI by Example", ch. 7 (memory).
Never imports pygame.

STATUS: sight, affordability, threat estimate and a fading memory of Ada's casts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from magic.rules import BattleState

THREAT_SMOOTHING = 0.5        # exponential moving average: half new evidence, half memory
WEAKNESS_MEMORY = 3           # turns a used weakness stays "fresh" in the foe's mind


@dataclass(frozen=True)
class Percept:
    """Everything a brain may know when it decides. Ratios are 0.0 to 1.0."""
    turn: int
    my_hp_ratio: float
    my_mp: int
    my_ward: int
    my_relevance: bool
    my_exhausted: bool
    ada_hp: int
    ada_hp_ratio: float
    ada_mp: int
    ada_ward: int
    ada_exhausted: bool
    ada_runes: frozenset[str]
    affordable: frozenset[str]           # actions whose spell the foe can pay for now
    threat: float                        # Ada's expected damage per turn, as a share of my max HP
    weakness_known: float                # 1.0: Ada just hit my weakness; fades to 0
    ada_overflowing: bool                # her last cast spilled off the page
    ada_last_runes: tuple[str, ...]      # technique signature of her last cast
    ada_casts_seen: int
    costs: dict[str, int] = field(default_factory=dict, compare=False)   # its own book

    def can(self, action: str) -> bool:
        return action in self.affordable

    def can_afford(self, *actions: str) -> bool:
        """Can it pay for all of these, one after the other (ignoring regeneration)?"""
        return all(a in self.costs for a in actions) and \
            sum(self.costs[a] for a in actions) <= self.my_mp


@dataclass
class Perception:
    """Builds a Percept every turn and keeps the memory between turns."""
    costs: dict[str, int]                # action -> MP cost, from the foe's own spellbook
    threat: float = 0.0
    last_weakness_turn: int | None = None
    seen: int = 0                        # how many of Ada's casts are already remembered
    log: list[str] = field(default_factory=list)   # what it noticed, for explain()

    def sense(self, state: BattleState) -> Percept:
        me, ada = state.foe, state.ada
        self.log = []
        for cast in state.ada_casts[self.seen:]:          # only the casts it has not seen yet
            if cast.scry:
                continue
            share = cast.damage / me.max_hp if me.max_hp else 0.0
            self.threat = THREAT_SMOOTHING * share + (1 - THREAT_SMOOTHING) * self.threat
            if cast.super_effective:
                self.last_weakness_turn = cast.turn
                self.log.append(f"turn {cast.turn}: she hit my weakness ({', '.join(cast.elements)})")
            if cast.overflow:
                self.log.append(f"turn {cast.turn}: her page overflowed")
        self.seen = len(state.ada_casts)
        casts = [c for c in state.ada_casts if not c.scry]
        last = casts[-1] if casts else None
        return Percept(
            turn=state.turn,
            my_hp_ratio=me.hp_ratio, my_mp=me.mp, my_ward=me.ward,
            my_relevance=me.relevance, my_exhausted=me.exhausted,
            ada_hp=ada.hp, ada_hp_ratio=ada.hp_ratio, ada_mp=ada.mp, ada_ward=ada.ward,
            ada_exhausted=ada.exhausted, ada_runes=frozenset(ada.runes),
            affordable=frozenset(a for a, cost in self.costs.items() if cost <= me.mp),
            threat=round(self.threat, 3),
            weakness_known=self._weakness_freshness(state.turn),
            ada_overflowing=bool(last and last.overflow),
            ada_last_runes=last.runes if last else (),
            ada_casts_seen=len(casts),
            costs=dict(self.costs),
        )

    def _weakness_freshness(self, turn: int) -> float:
        if self.last_weakness_turn is None:
            return 0.0
        age = turn - self.last_weakness_turn
        return max(0.0, 1.0 - age / WEAKNESS_MEMORY)


def summary(p: Percept) -> str:
    """One line for the F1 overlay."""
    return (f"me hp {p.my_hp_ratio:.0%} mp {p.my_mp}{' REL' if p.my_relevance else ''} | "
            f"ada hp {p.ada_hp_ratio:.0%} mp {p.ada_mp} ward {p.ada_ward} | "
            f"threat {p.threat:.2f} weakness {p.weakness_known:.1f}")
