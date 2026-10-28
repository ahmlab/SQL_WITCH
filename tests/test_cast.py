import random

import pytest

from magic.cast import PAGE_ROWS, PAGE_WIDTH, load_state, resolve, split_page
from magic.db import build_db
from magic.guard import Miscast

ALL_RUNES = {"WHERE", "ORDER BY", "LIMIT", "JOIN", "GROUP BY", "HAVING",
             "DISTINCT", "SUBQUERY", "WITH", "IS NULL", "COALESCE"}


@pytest.fixture
def battle():
    """A fresh level-1 battle against the Slime, with every rune unlocked for testing."""
    conn = build_db(level=1)
    state = load_state(conn, foe_id=1, seed=1)
    state.ada.runes = set(ALL_RUNES)
    state.foe.runes = {"WHERE", "LIMIT"}
    return conn, state, random.Random(1)


def test_load_state_reads_the_tables(battle):
    _, state, _ = battle
    assert (state.ada.name, state.ada.hp, state.ada.mp, state.ada.mp_regen) == ("Ada", 60, 30, 5)
    assert (state.foe.name, state.foe.hp, state.foe.element) == ("Asterisk Slime", 140, "Nature")


def test_split_page_cuts_rows_and_columns():
    columns = ["a" * 20, "b" * 15, "c" * 5]
    rows = [(1, 2, 3)] * 6
    page = split_page(columns, rows)
    assert len(page.visible_rows) == PAGE_ROWS and len(page.hidden_rows) == 2
    assert page.visible_columns == [0, 1]          # 20 + 1 + 15 = 36 fits exactly
    wide = split_page(["x" * (PAGE_WIDTH + 1)], [(1,)])
    assert wide.visible_columns == []


def test_select_star_at_level_one_casts_four_and_drains_the_rest(battle):
    conn, state, rng = battle
    state.ada.runes = set()                        # the Glade: SELECT and FROM only
    report = resolve(conn, state, "SELECT * FROM spells", "ada", rng)
    assert [c.spell for c in report.casts] == ["Ember", "Water Jet", "Thorn Whip", "Spark"]
    assert report.mp_spent == 30 and state.ada.mp == 0
    assert report.overflow == 8
    assert state.ada.exhausted
    assert report.status_line() == "12 rows | 4 cast | 8 lost | MP 30 -> 0"
    assert state.foe.hp < 140


def test_a_precise_query_casts_one_spell_and_keeps_mp(battle):
    conn, state, rng = battle
    report = resolve(conn, state, "SELECT name FROM spells WHERE element = 'Fire' LIMIT 1",
                     "ada", rng)
    assert [(c.spell, c.target) for c in report.casts] == [("Ember", "Asterisk Slime")]
    assert report.casts[0].effective == 2.0
    assert state.ada.mp == 27 and not state.ada.exhausted
    assert report.overflow == 0


def test_duplicates_fizzle_but_still_cost_mp(battle):
    conn, state, rng = battle
    # Two items in the satchel -> the cross join returns Ember twice.
    report = resolve(conn, state, "SELECT s.name FROM spells s, items i WHERE s.name = 'Ember'",
                     "ada", rng)
    assert len(report.casts) == 1
    assert [f.reason for f in report.fizzles] == ["duplicate"]
    assert state.ada.mp == 24


def test_a_scry_is_free_and_does_not_end_the_turn(battle):
    conn, state, rng = battle
    report = resolve(conn, state, "SELECT * FROM enemies", "ada", rng)
    assert report.scry and not report.ends_turn
    assert report.casts == [] and state.ada.mp == 30
    assert state.scries_used == 1


def test_the_fourth_scry_in_a_turn_is_spent_as_the_cast(battle):
    conn, state, rng = battle
    for _ in range(3):
        assert not resolve(conn, state, "SELECT * FROM enemies", "ada", rng).ends_turn
    assert resolve(conn, state, "SELECT * FROM enemies", "ada", rng).ends_turn


def test_stats_come_from_the_table_not_from_the_query(battle):
    conn, state, rng = battle
    report = resolve(conn, state, "SELECT name, 9999 AS power, 0 AS mp_cost FROM spells "
                     "WHERE name = 'Ember'", "ada", rng)
    assert report.casts[0].damage <= round(18 * 2.0 * 1.5)   # Ember, super effective, crit
    assert state.ada.mp == 27


def test_a_name_in_a_clipped_column_cannot_be_read(battle):
    conn, state, rng = battle
    # kind + element + power + mp_cost + unlock_level is wider than the page, so name is clipped.
    report = resolve(conn, state, "SELECT kind, element, power, mp_cost, unlock_level, name "
                     "FROM spells LIMIT 1", "ada", rng)
    assert report.casts == []
    assert [f.reason for f in report.fizzles] == ["overflow"]
    assert state.ada.mp == 27                     # it still drained Ember's cost


def test_a_combatant_name_in_the_row_is_the_target(battle):
    conn, state, rng = battle
    report = resolve(conn, state, "SELECT s.name, w.name FROM spells s, witch w "
                     "WHERE s.name = 'Ember'", "ada", rng)
    assert report.casts[0].target == "Ada"        # the contract is honest: she hit herself
    assert state.ada.hp < 60 and state.foe.hp == 140


def test_heals_and_wards_default_to_the_caster(battle):
    conn, state, rng = battle
    state.ada.hp = 20
    resolve(conn, state, "SELECT name FROM spells WHERE kind = 'heal' OR kind = 'ward'",
            "ada", rng)
    assert state.ada.hp == 50 and state.ada.ward == 20


def test_an_item_is_used_and_its_quantity_drops(battle):
    conn, state, rng = battle
    state.ada.mp = 5
    report = resolve(conn, state, "SELECT name FROM items WHERE kind = 'mp' AND qty > 0 LIMIT 1",
                     "ada", rng)
    assert report.casts[0].spell == "Ether" and state.ada.mp == 15
    assert conn.execute("SELECT qty FROM items WHERE name = 'Ether'").fetchone()[0] == 1


def test_when_mp_runs_out_the_rest_fizzle(battle):
    conn, state, rng = battle
    state.ada.mp = 4
    report = resolve(conn, state, "SELECT name FROM spells WHERE mp_cost = 3 LIMIT 2",
                     "ada", rng)
    assert len(report.casts) == 1
    assert [f.reason for f in report.fizzles] == ["no_mana"]
    assert state.ada.mp == 0


def test_the_slime_casts_through_the_same_pipeline(battle):
    conn, state, rng = battle
    report = resolve(conn, state, "SELECT * FROM foe_spells WHERE foe_id = 1", "foe", rng)
    assert [c.spell for c in report.casts] == ["Goo Spit", "Sticky Slap", "Bubble Pop",
                                              "Ooze Splash"]
    assert all(c.target == "Ada" for c in report.casts)
    assert state.foe.mp == 0 and state.foe.exhausted
    assert state.ada.hp < 60
    assert state.foe_book == ["SELECT * FROM foe_spells WHERE foe_id = 1"]


def test_ada_cannot_cast_the_slimes_spells(battle):
    conn, state, rng = battle
    report = resolve(conn, state, "SELECT * FROM foe_spells", "ada", rng)
    assert report.scry and report.casts == []


def test_every_query_is_written_to_the_log(battle):
    conn, state, rng = battle
    resolve(conn, state, "SELECT name FROM spells WHERE element = 'Fire' LIMIT 1", "ada", rng)
    resolve(conn, state, "SELECT * FROM enemies", "ada", rng)
    log = conn.execute("SELECT turn, caster, clauses, rows_out, rows_cast, seed "
                       "FROM query_log").fetchall()
    assert log == [(1, "Ada", "LIMIT,WHERE", 1, 1, 1), (1, "Ada", "", 1, 0, 1)]


def test_the_tables_mirror_the_battle_after_a_cast(battle):
    conn, state, rng = battle
    resolve(conn, state, "SELECT name FROM spells WHERE element = 'Fire' LIMIT 1", "ada", rng)
    assert conn.execute("SELECT hp FROM enemies WHERE id = 1").fetchone()[0] == state.foe.hp
    assert conn.execute("SELECT mp FROM witch").fetchone()[0] == 27


def test_a_miscast_changes_nothing(battle):
    conn, state, rng = battle
    state.ada.runes = set()
    with pytest.raises(Miscast):
        resolve(conn, state, "SELECT name FROM spells LIMIT 1", "ada", rng)
    assert state.ada.mp == 30
    assert conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0] == 0


def test_same_seed_same_battle():
    def play(seed):
        conn = build_db()
        state = load_state(conn, seed=seed)
        report = resolve(conn, state, "SELECT * FROM spells", "ada", random.Random(seed))
        return [c.damage for c in report.casts]
    assert play(3) == play(3)
