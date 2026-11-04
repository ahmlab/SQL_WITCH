"""One battle, round by round (design doc 4.1). Shared by the terminal game and the window.

The battle is a small step machine instead of a loop, so the pygame scene can drive it one
event at a time and the terminal can drive it with input(). Either way the order is:
the guardian opens the first round (so the player reads a query before writing one), then
the faster side acts first; Ada may scry up to SCRY_PER_TURN times, then casts one query;
the foe perceives, decides, writes its SQL and casts it; then the round ends.
Never imports pygame.

STATUS: any guardian from ai/roster.py, guardian opens, Ada's casts remembered, Invitation.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass

from ai.roster import GUARDIANS, Guardian
from magic import rules
from magic.cast import CastReport, load_state, resolve, sync_state
from magic.db import build_db


@dataclass
class FoeTurn:
    """What the foe did. The intent is not kept: only the SQL and its result matter."""
    sql: str
    report: CastReport
    reasoning: dict              # brain.explain(), for the F1 overlay
    invitation: str | None       # a rune Ada just learned from the foe's book
    movement: object = None      # the brain's steering order (ai.steering.Movement), if any


@dataclass
class RoundEnd:
    """What happened at the end of a round, for the renderer."""
    turn: int                    # the round that just ended
    mp_gained: dict[str, int]
    winner: str | None


class Battle:
    def __init__(self, seed: int, guardian: str = "slime", brain=None,
                 ada_runes: set[str] | None = None, level: int | None = None,
                 foe_opens: bool = True):
        self.guardian: Guardian = GUARDIANS[guardian]
        g = self.guardian
        # One random generator for the whole battle: same seed, same battle (design doc 5.10).
        self.rng = random.Random(seed)
        self.seed = seed
        self.conn = build_db(level or g.level, foe_ids=[g.foe_id])
        self.state = load_state(self.conn, foe_id=g.foe_id, seed=seed)
        # The Glade assumes nothing beyond SELECT and FROM; each guardian then adds its rune.
        self.state.ada.runes = set(g.ada_runes if ada_runes is None else ada_runes)
        self.state.foe.runes = set(g.runes)
        self.chart = rules.load_type_chart(self.conn)
        self.brain = brain if brain is not None else g.make_brain(self.conn)
        self.foe_opens = foe_opens
        self.foe_turns = 0
        self.winner: str | None = None
        self.queue: list[str] = []
        self.last_round: RoundEnd | None = None
        self._start_round()

    # ------------------------------------------------------------ whose turn

    @property
    def whose_turn(self) -> str:
        """'ada', 'foe' or 'over'."""
        return "over" if self.winner else self.queue[0]

    def _start_round(self) -> None:
        if self.foe_opens and self.state.turn == 1:
            first = "foe"          # the guardian teaches by example: its query comes first
        else:
            first = rules.first_mover(self.state, self.rng)
        self.queue = [first, "foe" if first == "ada" else "ada"]
        rules.start_turn(self.state, first)

    def _advance(self) -> None:
        """The current side is done: check for a winner, then pass the turn or end the round."""
        self.winner = rules.winner(self.state)
        if self.winner:
            return
        self.queue.pop(0)
        if self.queue:
            rules.start_turn(self.state, self.queue[0])
            return
        before = {"ada": self.state.ada.mp, "foe": self.state.foe.mp}
        turn = self.state.turn
        self.winner = rules.end_of_round(self.state)
        gained = {"ada": self.state.ada.mp - before["ada"],
                  "foe": self.state.foe.mp - before["foe"]}
        self.last_round = RoundEnd(turn, gained, self.winner)
        sync_state(self.conn, self.state)      # the regenerated MP must be visible to queries
        if not self.winner:
            self._start_round()

    # ------------------------------------------------------------ the two sides

    def ada_cast(self, sql: str) -> CastReport:
        """Ada's query. Raises guard.Miscast for a rejected query; in Apprentice mode a miscast
        is free, so her turn simply continues. A scry does not end the turn either."""
        if self.whose_turn != "ada":
            raise RuntimeError(f"It is not Ada's turn ({self.whose_turn}).")
        self.last_round = None
        report = resolve(self.conn, self.state, sql, "ada", self.rng, self.chart)
        self.state.ada_casts.append(self._remember(report))   # what the foe can perceive
        if report.ends_turn:
            self._advance()
        return report

    def _remember(self, report: CastReport) -> rules.CastMemory:
        foe = self.state.foe.name
        hits = [c for c in report.casts if c.kind in ("attack", "area") and c.target == foe]
        return rules.CastMemory(
            turn=self.state.turn, runes=tuple(sorted(report.runes)),
            elements=tuple(c.element for c in report.casts if c.element),
            damage=sum(c.damage for c in hits),
            super_effective=any(c.effective >= rules.SUPER_EFFECTIVE for c in hits),
            overflow=report.overflow, scry=report.scry)

    def foe_act(self) -> FoeTurn:
        """The foe's five-stage loop (design doc 5.1): perceive, decide, express, execute, reveal."""
        if self.whose_turn != "foe":
            raise RuntimeError(f"It is not the foe's turn ({self.whose_turn}).")
        self.last_round = None
        self.foe_turns += 1
        snapshot = copy.deepcopy(self.state)                  # perceive: a copy it cannot change
        intent = self.brain.decide(snapshot, self.rng)        # decide
        reasoning = self.brain.explain()
        movement = getattr(self.brain, "movement", None)
        sql = self.guardian.style(intent, self.state, self.foe_turns)   # express
        del intent                                            # from here on only the SQL counts
        report = resolve(self.conn, self.state, sql, "foe", self.rng, self.chart)  # execute
        invitation = self._invitation(report)                 # reveal
        self._advance()
        return FoeTurn(sql, report, reasoning, invitation, movement)

    def _invitation(self, report: CastReport) -> str | None:
        """When the foe's signature rune appears in its book, Ada may copy it (design doc 3.6)."""
        rune = self.guardian.signature
        if rune in report.runes and rune not in self.state.ada.runes:
            self.state.ada.runes.add(rune)
            return rune
        return None
