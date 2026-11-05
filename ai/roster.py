"""The guardians of this build, in the order Ada meets them (design doc 5.2).

Each Guardian bundles what a battle needs: which foe row, Ada's level for the fight, the
brain, the SQL style, the runes the guardian can write and the one it teaches.
Never imports pygame.

STATUS: the Asterisk Slime and Sir Wherewell.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ai.fsm import SlimeBrain
from ai.knight import ACTION_SPELLS, KnightBrain
from ai.styles import (KNIGHT_RUNES, KNIGHT_SIGNATURE, SLIME_RUNES, SLIME_SIGNATURE,
                       render_knight, render_slime)


@dataclass(frozen=True)
class Guardian:
    key: str
    foe_id: int
    level: int                                   # Ada's level in this fight (data/levels.csv)
    runes: frozenset[str]                        # what the guardian can write
    signature: str                               # the rune the Invitation hands to Ada
    ada_runes: frozenset[str]                    # what Ada already knows when it starts
    style: Callable
    make_brain: Callable                         # (sqlite connection) -> brain


def _slime_brain(conn) -> SlimeBrain:
    cheapest = conn.execute("SELECT MIN(mp_cost) FROM foe_spells WHERE foe_id = 1").fetchone()[0]
    return SlimeBrain({"splat": cheapest, "careful": cheapest})


def _knight_brain(conn) -> KnightBrain:
    costs = {}
    for action, spell in ACTION_SPELLS.items():
        row = conn.execute("SELECT mp_cost FROM foe_spells WHERE foe_id = 2 AND name = ?",
                           (spell,)).fetchone()
        if row:
            costs[action] = row[0]
    return KnightBrain(costs)


GUARDIANS = {
    "slime": Guardian("slime", 1, 1, frozenset(SLIME_RUNES), SLIME_SIGNATURE, frozenset(),
                      render_slime, _slime_brain),
    "knight": Guardian("knight", 2, 2, frozenset(KNIGHT_RUNES), KNIGHT_SIGNATURE,
                       frozenset({"LIMIT"}), render_knight, _knight_brain),
}
ORDER = ["slime", "knight"]


def next_guardian(key: str) -> str | None:
    i = ORDER.index(key)
    return ORDER[i + 1] if i + 1 < len(ORDER) else None
