"""Style grammars: each foe writes its intent as SQL in its own voice (design doc 5.1).

After rendering, the intent is discarded. The query then goes through magic.cast.resolve()
exactly like Ada's, so whatever the brain "wanted", only the executed result can hurt anyone.
Never imports pygame.

STATUS: step 3 done - the Slime's sloppy SELECT * with the LIMIT teaching guarantee.
"""

from __future__ import annotations

from ai.base import Intent
from magic import guard
from magic.rules import BattleState

SLIME_RUNES = {"WHERE", "LIMIT"}        # the keywords the Slime is able to write
SLIME_SIGNATURE = "LIMIT"               # the rune the Invitation hands to Ada (design doc 3.6)
GUARANTEE_TURN = 3                      # the signature appears within the foe's first 3 turns

SLIME_ATTACK = "SELECT * FROM foe_spells WHERE foe_id = {foe_id}"
SLIME_CAREFUL = SLIME_ATTACK + " LIMIT 2"
# Wobbling and panting are still real queries: SELECT * on tables with no spell in them,
# so they cast nothing. That is how "regain MP" and "skip turn" happen without cheating.
SLIME_LOOKS = {
    "wobble": "SELECT * FROM enemies WHERE id = {foe_id}",
    "exhausted": "SELECT * FROM witch WHERE hp > 0",
}


def book_uses(state: BattleState, rune: str) -> bool:
    """Has this rune already been printed in the foe's book?"""
    return any(rune in guard.runes_used(guard.parse_one_select(sql)) for sql in state.foe_book)


def render_slime(intent: Intent, state: BattleState, turn: int) -> str:
    """Write the Slime's intent as SQL. `turn` is the Slime's own turn count, starting at 1."""
    foe_id = state.foe_id
    # Teaching guarantee: whatever the intent, LIMIT must show up by the third turn.
    if turn >= GUARANTEE_TURN and not book_uses(state, SLIME_SIGNATURE):
        return SLIME_CAREFUL.format(foe_id=foe_id)
    if intent.kind == "scry":
        return SLIME_LOOKS[intent.action].format(foe_id=foe_id)
    if intent.params.get("limit"):
        return SLIME_ATTACK.format(foe_id=foe_id) + f" LIMIT {intent.params['limit']}"
    return SLIME_ATTACK.format(foe_id=foe_id)
