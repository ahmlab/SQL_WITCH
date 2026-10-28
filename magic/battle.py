"""One battle, round by round (design doc 4.1). Shared by the terminal game and the window.

The battle is a small step machine instead of a loop, so the pygame scene can drive it one
event at a time and the terminal can drive it with input(). Either way the order is:
the faster side acts first; Ada may scry up to SCRY_PER_TURN times, then casts one query;
the foe perceives, decides, writes its SQL and casts it; then the round ends.
Never imports pygame.

STATUS: step 4 done - rounds, turns, the foe's five-stage loop and the Invitation.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass

from ai.fsm import SlimeBrain
from ai.styles import SLIME_RUNES, SLIME_SIGNATURE, render_slime
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


@dataclass
class RoundEnd:
    """What happened at the end of a round, for the renderer."""
    turn: int                    # the round that just ended
    mp_gained: dict[str, int]
    winner: str | None


class Battle:
    def __init__(self, seed: int, level: int = 1, foe_id: int = 1, brain=None,
                 ada_runes: set[str] | None = None):
        # One random generator for the whole battle: same seed, same battle (design doc 5.10).
        self.rng = random.Random(seed)
        self.seed = seed
        self.conn = build_db(level)
        self.state = load_state(self.conn, foe_id=foe_id, seed=seed)
        # The Glade assumes nothing beyond SELECT and FROM; LIMIT comes from the Slime.
        self.state.ada.runes = set(ada_runes or ())
        self.state.foe.runes = set(SLIME_RUNES)
        self.chart = rules.load_type_chart(self.conn)
        self.brain = brain if brain is not None else SlimeBrain()
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
        if report.ends_turn:
            self._advance()
        return report

    def foe_act(self) -> FoeTurn:
        """The foe's five-stage loop (design doc 5.1): perceive, decide, express, execute, reveal."""
        if self.whose_turn != "foe":
            raise RuntimeError(f"It is not the foe's turn ({self.whose_turn}).")
        self.last_round = None
        self.foe_turns += 1
        snapshot = copy.deepcopy(self.state)                  # perceive: a copy it cannot change
        intent = self.brain.decide(snapshot, self.rng)        # decide
        reasoning = self.brain.explain()
        sql = render_slime(intent, self.state, self.foe_turns)   # express
        del intent                                            # from here on only the SQL counts
        report = resolve(self.conn, self.state, sql, "foe", self.rng, self.chart)  # execute
        invitation = self._invitation(report)                 # reveal
        self._advance()
        return FoeTurn(sql, report, reasoning, invitation)

    def _invitation(self, report: CastReport) -> str | None:
        """When the foe's signature rune appears in its book, Ada may copy it (design doc 3.6)."""
        if SLIME_SIGNATURE in report.runes and SLIME_SIGNATURE not in self.state.ada.runes:
            self.state.ada.runes.add(SLIME_SIGNATURE)
            return SLIME_SIGNATURE
        return None
