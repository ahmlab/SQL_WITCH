"""Items, pressure guardians, Insight and the simulator bands (prompt 08 §3)."""

import random

import pytest

from ai.pressure import PRESSURE
from magic.battle import EXPLORATION, INSIGHT, Battle
from magic.cast import load_state, resolve
from magic.db import build_db
from sim.bots import BOTS, attack_only, competent, first_attempt_satchel, play, win_rate

TARGET = (0.60, 0.75)


# ------------------------------------------------------------------ the simulator

@pytest.mark.parametrize("guardian", ["slime", "knight"])
def test_each_act1_guardian_is_in_the_target_band_for_the_competent_bot(guardian):
    rate = win_rate(guardian, "competent", range(200))
    assert TARGET[0] <= rate <= TARGET[1], rate


@pytest.mark.parametrize("guardian", ["slime", "knight"])
def test_the_attack_only_bot_loses_to_both_pressure_guardians(guardian):
    assert win_rate(guardian, "attack_only", range(100)) < 0.40


def test_bots_are_deterministic_and_never_touch_the_battle_rng():
    a = play("slime", competent(), 11)
    b = play("slime", competent(), 11)
    assert a.conn.execute("SELECT sql FROM query_log").fetchall() == \
        b.conn.execute("SELECT sql FROM query_log").fetchall()


# ------------------------------------------------------------------ pressure

def test_the_slime_telegraphs_its_big_turn_with_a_readable_query_then_casts_it():
    spec = PRESSURE["slime"]
    battle = play("slime", attack_only(), 3)
    book = battle.state.foe_book
    telegraph = spec["telegraph_sql"].format(foe_id=1)
    assert telegraph in book
    i = book.index(telegraph)
    assert book[i + 1] == spec["strike_sql"].format(foe_id=1)


def test_a_ward_softens_the_telegraphed_big_turn():
    def strike(ward):
        conn = build_db(level=1, foe_ids=[1])
        state = load_state(conn, foe_id=1)
        state.ada.ward = ward
        report = resolve(conn, state, PRESSURE["slime"]["strike_sql"].format(foe_id=1), "foe",
                         random.Random(2))
        return report.casts[0].damage
    assert strike(30) < strike(0) - 20


def test_the_knights_aegis_turns_spells_aside_and_rust_salts_strip_it():
    conn = build_db(level=2, foe_ids=[2], inventory={"Rust Salts": 1})
    state = load_state(conn, foe_id=2)
    resolve(conn, state, PRESSURE["knight"]["sql"].format(foe_id=2), "foe", random.Random(1))
    assert state.foe.aegis > 0
    hp = state.foe.hp
    report = resolve(conn, state, "SELECT name FROM spells WHERE name = 'Thunderclap'", "ada",
                     random.Random(1))
    assert state.foe.hp == hp and report.casts[0].deflected
    report = resolve(conn, state, "SELECT name FROM items WHERE kind = 'cleanse'", "ada",
                     random.Random(1))
    assert state.foe.aegis == 0 and report.casts[0].kind == "item"
    resolve(conn, state, "SELECT name FROM spells WHERE name = 'Thunderclap'", "ada",
            random.Random(1))
    assert state.foe.hp < hp


def test_the_aegis_fades_with_the_rounds_so_it_never_locks_a_fight():
    from magic import rules
    conn = build_db(level=2, foe_ids=[2])
    state = load_state(conn, foe_id=2)
    state.foe.aegis = 2
    rules.end_of_round(state)
    rules.end_of_round(state)
    assert state.foe.aegis == 0


# ------------------------------------------------------------------ items

def kinds_state(**inventory):
    conn = build_db(level=1, foe_ids=[1], inventory=inventory)
    return conn, load_state(conn, foe_id=1)


def test_every_item_kind_does_what_the_data_says():
    conn, state = kinds_state(**{"Warding Charm": 1, "Scrying Lens": 1, "Hourglass Charm": 1})
    resolve(conn, state, "SELECT name FROM items WHERE kind = 'ward'", "ada", random.Random(1))
    assert state.ada.ward == 30
    resolve(conn, state, "SELECT name FROM items WHERE kind = 'scry'", "ada", random.Random(1))
    assert state.extra_looks == 2
    resolve(conn, state, "SELECT name FROM items WHERE kind = 'snapshot'", "ada", random.Random(1))
    assert state.free_rewinds == 1


def test_a_lens_gives_more_free_looks_next_turn():
    from magic import rules
    conn, state = kinds_state(**{"Scrying Lens": 1})
    state.extra_looks = 2
    rules.start_turn(state, "ada")
    assert state.scries_used == -2                 # 3 + 2 looks this turn


def test_an_hourglass_makes_the_next_rewind_cost_no_turn():
    battle = Battle(seed=2, foe_opens=False, inventory={"Hourglass Charm": 1})
    while battle.whose_turn != "ada":
        battle.foe_act()
    battle.ada_cast("SELECT name FROM items WHERE kind = 'snapshot'")
    while battle.whose_turn != "ada":
        battle.foe_act()
    report = battle.rewind(len(battle.world.snapshots) - 1)
    assert not report.ends_turn and battle.whose_turn == "ada"


def test_the_satchel_comes_from_the_save_and_items_she_lacks_are_not_in_it():
    conn = build_db(level=1, foe_ids=[1], inventory={"Ether": 3})
    assert conn.execute("SELECT name, qty FROM items").fetchall() == [("Ether", 3)]


def test_the_first_attempt_satchel_includes_earlier_drops():
    satchel = first_attempt_satchel("knight")
    for name, qty in EXPLORATION["drops"]["slime"].items():
        assert satchel[name] >= qty


# ------------------------------------------------------------------ Insight

def test_insight_triggers_once_per_table_per_battle():
    battle = Battle(seed=4, foe_opens=False)
    while battle.whose_turn != "ada":
        battle.foe_act()
    battle.state.ada.mp = 10
    first = battle.ada_cast("SELECT * FROM enemies")
    assert first.insight == ["enemies"] and battle.state.ada.mp == 10 + INSIGHT["mp"]
    again = battle.ada_cast("SELECT name, hp FROM enemies")
    assert again.insight == [] and battle.state.ada.mp == 10 + INSIGHT["mp"]
    other = battle.ada_cast("SELECT * FROM type_chart")
    assert other.insight == ["type_chart"]
    assert battle.codex.knows(INSIGHT["codex"])


def test_a_cast_is_not_an_insight():
    battle = Battle(seed=4, foe_opens=False)
    while battle.whose_turn != "ada":
        battle.foe_act()
    report = battle.ada_cast("SELECT name FROM spells LIMIT 1")
    assert report.insight == []
