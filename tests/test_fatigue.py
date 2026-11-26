"""Fatigue and Focus (prompt 08 §1): the meter, its bands, the page it leaves, the faint."""

import random

import pytest

from magic.battle import Battle
from magic.cast import PAGE_ROWS, load_state, resolve
from magic.db import build_db
from magic.fatigue import BANDS, TUNING, Fatigue, band_of
from magic.guard import Miscast

FOUR_EMBERS = "SELECT name FROM spells WHERE name = 'Ember'"


def test_bands_cover_the_meter_and_shrink_the_page():
    assert [b.rows for b in BANDS] == [4, 3, 2, 2]
    assert band_of(0.0).id == "rested" and band_of(1.0).faint
    assert Fatigue(0.0).page_rows() == PAGE_ROWS
    assert Fatigue(0.5).page_rows() == 3
    assert Fatigue(0.8).page_rows() == 2


@pytest.mark.parametrize("value, rows", [(0.1, 4), (0.5, 3), (0.8, 2)])
def test_fatigue_bands_change_the_rows_of_a_cast_report(value, rows):
    battle = Battle(seed=3, foe_opens=False, fatigue=Fatigue(value))
    while battle.whose_turn != "ada":
        battle.foe_act()
    report = battle.ada_cast("SELECT name FROM spells")      # more rows than any page
    assert report.page_rows == rows
    assert report.visible == rows
    assert report.overflow == len([r for r in report.rows]) - rows


def test_resolve_cuts_at_the_page_it_is_given():
    conn = build_db(level=1, foe_ids=[1])
    state = load_state(conn, foe_id=1)
    report = resolve(conn, state, "SELECT name FROM spells", "ada", random.Random(1), page_rows=2)
    assert report.page_rows == 2 and len(report.casts) + len(report.fizzles) == len(report.rows)
    assert all(c.row < 2 for c in report.casts)


class _Report:
    def __init__(self, casts=1, overflow=0, fizzles=()):
        self.casts, self.overflow, self.fizzles = [object()] * casts, overflow, list(fizzles)


def test_focus_adds_a_row_only_after_n_clean_casts():
    f = Fatigue(0.0)
    need = TUNING["focus"]["streak"]
    for _ in range(need - 1):
        f.note(_Report())
        assert f.page_rows() == 4
    f.note(_Report())
    assert f.focused and f.page_rows() == 5
    for _ in range(TUNING["focus"]["lasts_casts"]):
        assert f.page_rows() == 5
        f.note(_Report())
    assert f.page_rows() == 4                                # short-lived


@pytest.mark.parametrize("sloppy", [_Report(overflow=2), _Report(fizzles=["x"]), None])
def test_any_sloppy_cast_resets_focus(sloppy):
    f = Fatigue(0.0)
    for _ in range(TUNING["focus"]["streak"]):
        f.note(_Report())
    assert f.focused
    f.note(sloppy)
    assert not f.focused and f.streak == 0


def test_looks_and_writes_neither_build_nor_break_focus():
    f = Fatigue(0.0)
    f.note(_Report())
    f.note(_Report(casts=0))
    assert f.streak == 1


def test_a_miscast_in_battle_breaks_the_streak():
    fatigue = Fatigue(0.0, streak=2)
    battle = Battle(seed=3, foe_opens=False, fatigue=fatigue)
    while battle.whose_turn != "ada":
        battle.foe_act()
    with pytest.raises(Miscast):
        battle.ada_cast("SELEC nonsense")
    assert fatigue.streak == 0


def test_rounds_and_casts_tire_the_witch():
    fatigue = Fatigue(0.0)
    battle = Battle(seed=3, fatigue=fatigue)
    while battle.whose_turn == "foe":
        battle.foe_act()
    battle.ada_cast(FOUR_EMBERS)
    while battle.whose_turn == "foe":
        battle.foe_act()
    rise = TUNING["rise"]
    assert fatigue.value == pytest.approx(rise["cast"] + rise["round"], abs=1e-4)


def test_rest_actions_follow_the_data():
    fall = TUNING["fall"]
    f = Fatigue(0.9)
    f.rest("meal")
    assert f.value == pytest.approx(0.9 - fall["meal"])
    before = f.value
    f.rest("letter")
    assert f.value == pytest.approx(before - fall["letter"]) and f.focused
    f.rest("sleep")
    assert f.value == 0.0


def test_a_spent_witch_faints_when_the_battle_ends_whatever_the_outcome():
    for value, faints in ((0.99, True), (0.3, False)):
        battle = Battle(seed=5, fatigue=Fatigue(value))
        guard_turns = 0
        while battle.whose_turn != "over" and guard_turns < 60:
            if battle.whose_turn == "foe":
                battle.foe_act()
            else:
                battle.ada_cast("SELECT name FROM spells WHERE name = 'Ember'")
            guard_turns += 1
        assert battle.whose_turn == "over"
        assert battle.winner in ("ada", "foe")
        assert battle.fainted is faints


def test_the_meter_survives_a_save_round_trip():
    from save.state import GameState
    f = Fatigue(0.42, streak=2, charges=1)
    state = GameState(fatigue=f.value, focus=f.to_dict())
    back = GameState.from_dict(state.to_dict())
    g = Fatigue.from_save(back.fatigue, back.focus)
    assert (g.value, g.streak, g.charges) == (0.42, 2, 1)
