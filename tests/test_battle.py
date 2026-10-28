import itertools
import subprocess
import sys
from pathlib import Path

import pytest

from ai.base import RandomBrain
from ai.fsm import slime_legal_intents
from magic.battle import Battle
from magic.guard import Miscast
from sim import play_cli

ROOT = Path(__file__).resolve().parent.parent


def fight(battle, ada_sql=lambda b: "SELECT name FROM spells", max_steps=200):
    """Play a whole battle with a scripted Ada. Returns the list of (side, sql) cast."""
    log = []
    for _ in range(max_steps):
        if battle.whose_turn == "over":
            return log
        if battle.whose_turn == "ada":
            sql = ada_sql(battle)
            battle.ada_cast(sql)
            log.append(("ada", sql))
        else:
            log.append(("foe", battle.foe_act().sql))
    raise AssertionError("the battle never ended")


def precise(battle):
    """A player who copies LIMIT as soon as the Slime shows it."""
    if "LIMIT" in battle.state.ada.runes:
        return "SELECT name FROM spells LIMIT 1"
    return "SELECT name FROM spells"


# ------------------------------------------------------------------ the round

def test_the_faster_side_acts_first():
    assert Battle(seed=1).whose_turn == "ada"          # Ada speed 5, Slime speed 3


def test_a_scry_keeps_the_turn_and_a_cast_passes_it():
    battle = Battle(seed=1)
    battle.ada_cast("SELECT * FROM enemies")
    assert battle.whose_turn == "ada"
    battle.ada_cast("SELECT name FROM spells")
    assert battle.whose_turn == "foe"


def test_a_miscast_is_free_in_apprentice_mode():
    battle = Battle(seed=1)
    with pytest.raises(Miscast):
        battle.ada_cast("SELECT name FROM spells LIMIT 1")   # LIMIT is still locked
    assert battle.whose_turn == "ada" and battle.state.ada.mp == 30


def test_acting_out_of_turn_is_refused():
    battle = Battle(seed=1)
    with pytest.raises(RuntimeError):
        battle.foe_act()


def test_end_of_round_regenerates_and_the_tables_see_it():
    battle = Battle(seed=1)
    battle.ada_cast("SELECT name FROM spells")         # drains Ada to 0
    battle.foe_act()
    assert battle.state.turn == 2
    assert battle.last_round.mp_gained["ada"] == 5
    assert battle.conn.execute("SELECT mp FROM witch").fetchone()[0] == 5


@pytest.mark.parametrize("seed", range(25))
def test_every_battle_ends(seed):
    battle = Battle(seed=seed)
    fight(battle, precise)
    assert battle.winner in ("ada", "foe")


def test_the_same_seed_replays_the_same_battle():
    def replay(seed):
        battle = Battle(seed=seed)
        fight(battle, precise)
        return battle.conn.execute("SELECT turn, caster, sql, rows_cast FROM query_log").fetchall()
    assert replay(4) == replay(4)
    assert len({tuple(replay(seed)) for seed in range(8)}) > 1


@pytest.mark.parametrize("seed", range(25))
def test_the_invitation_teaches_limit_within_three_slime_turns(seed):
    # A passive Ada (four looks per turn, no spells) lets the Slime live long enough.
    battle = Battle(seed=seed)
    for _ in range(3):
        while battle.whose_turn == "ada":
            battle.ada_cast("SELECT * FROM enemies")
        if battle.whose_turn == "over":
            break
        battle.foe_act()
    assert "LIMIT" in battle.state.ada.runes


def test_the_foe_turn_reports_sql_and_reasoning_but_not_the_intent():
    battle = Battle(seed=2)
    battle.ada_cast("SELECT name FROM spells")
    turn = battle.foe_act()
    assert turn.sql.startswith("SELECT * FROM")
    assert "state" in turn.reasoning
    assert not hasattr(turn, "intent")


def test_any_brain_can_drive_the_slime():
    battle = Battle(seed=3, brain=RandomBrain(slime_legal_intents))
    fight(battle, precise)
    assert battle.winner in ("ada", "foe")


def test_the_brain_cannot_change_the_real_state():
    class Cheater:
        def decide(self, state, rng):
            state.ada.hp = 0                            # tries to win by perceiving harder
            return slime_legal_intents(state)[0]

        def explain(self):
            return {}

    battle = Battle(seed=1, brain=Cheater())
    battle.ada_cast("SELECT name FROM spells")
    battle.foe_act()
    assert battle.state.ada.hp == 60


# ------------------------------------------------------------------ the terminal

def run_cli(lines, seed=7):
    out = []
    feed = iter(lines)

    def read(prompt):
        try:
            return next(feed)
        except StopIteration:
            raise EOFError

    play_cli.main(["--seed", str(seed)], read=read, out=out.append)
    return "\n".join(out)


def test_the_cli_plays_a_whole_battle():
    script = ["SELECT * FROM enemies", "DROP TABLE spells", ":why", ":schema", ":help"]
    text = run_cli(itertools.chain(script, itertools.repeat("SELECT name FROM spells", 40)))
    assert "the page ends here: 8 rows kept writing themselves into the margin" in text
    assert "MY LIFE" in text
    assert "MP: 30 -> 0" in text
    assert "foe_spells: foe_id, name" in text
    assert "Ada wins!" in text or "Game over." in text


def test_the_cli_quits_cleanly():
    text = run_cli([":quit"])
    assert "Round 1" in text and "wins" not in text


def test_the_cli_never_imports_pygame():
    code = "import sys, sim.play_cli; sys.exit('pygame' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0
