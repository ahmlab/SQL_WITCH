import random

import pytest

from magic.db import build_db
from magic.rules import (BattleState, Combatant, apply_hit, damage, end_of_round,
                         first_mover, heal, load_type_chart, start_turn, winner)


@pytest.fixture(scope="module")
def chart():
    return load_type_chart(build_db())


def slime(**overrides):
    stats = dict(name="Asterisk Slime", hp=140, max_hp=140, mp=20, max_mp=20, mp_regen=5,
                 speed=3, element="Nature", weakness="Fire")
    stats.update(overrides)
    return Combatant(**stats)


def ada(**overrides):
    stats = dict(name="Ada", hp=60, max_hp=60, mp=30, max_mp=30, mp_regen=5,
                 speed=5, element="Arcane")
    stats.update(overrides)
    return Combatant(**stats)


def test_chart_is_read_from_the_database(chart):
    assert len(chart) == 110
    assert chart[("Fire", "Nature")] == 2.0


def test_fire_is_super_effective_against_nature(chart):
    hit = damage(18, "Fire", slime(), chart, random.Random(1))
    assert hit.multiplier == 2.0


@pytest.mark.parametrize("seed", range(200))
def test_damage_stays_inside_the_roll_bounds(chart, seed):
    hit = damage(18, "Fire", slime(), chart, random.Random(seed))
    base = 18 * 2.0
    crit = 1.5 if hit.crit else 1.0
    assert round(base * 0.85 * crit) <= hit.amount <= round(base * 1.0 * crit)


def test_same_seed_gives_the_same_hit(chart):
    a = damage(18, "Fire", slime(), chart, random.Random(7))
    b = damage(18, "Fire", slime(), chart, random.Random(7))
    assert a == b


def test_ward_absorbs_and_is_used_up(chart):
    target = ada(ward=10)
    hit = damage(20, "Arcane", target, chart, random.Random(3))
    raw = hit.amount + hit.absorbed
    assert hit.absorbed == min(10, raw)
    apply_hit(target, hit)
    assert target.ward == 10 - hit.absorbed
    assert target.hp == 60 - hit.amount


def test_a_ward_bigger_than_the_hit_soaks_all_of_it(chart):
    target = ada(ward=100)
    hit = damage(5, "Nature", target, chart, random.Random(0))
    assert hit.amount == 0 and hit.absorbed > 0


def test_null_element_defends_as_void(chart):
    void = slime(element=None)
    assert damage(10, "Arcane", void, chart, random.Random(0)).multiplier == 2.0
    assert damage(10, "Fire", void, chart, random.Random(0)).multiplier == 0.5


def test_exhausted_target_takes_one_and_a_half(chart):
    tired = damage(20, "Arcane", slime(exhausted=True), chart, random.Random(4))
    replay = random.Random(4)                  # the same two draws damage() makes
    roll = replay.uniform(0.85, 1.0)
    crit = 1.5 if replay.random() < 1 / 16 else 1.0
    assert tired.amount == round(20 * roll * crit * 1.5)


def test_hp_never_goes_below_zero_or_above_max(chart):
    target = slime(hp=3)
    apply_hit(target, damage(100, "Fire", target, chart, random.Random(0)))
    assert target.hp == 0
    healed = ada(hp=55)
    assert heal(healed, 30) == 5 and healed.hp == 60


def test_mp_never_exceeds_max():
    state = BattleState(ada=ada(mp=28), foe=slime(mp=20))
    end_of_round(state)
    assert state.ada.mp == 30
    assert state.foe.mp == 20


def test_end_of_round_regenerates_decays_wards_and_counts():
    state = BattleState(ada=ada(mp=0, ward=9), foe=slime(mp=0))
    assert end_of_round(state) is None
    assert (state.ada.mp, state.foe.mp) == (5, 5)
    assert state.ada.ward == 4
    assert state.turn == 2


def test_end_of_round_reports_the_winner():
    assert end_of_round(BattleState(ada=ada(), foe=slime(hp=0))) == "ada"
    assert end_of_round(BattleState(ada=ada(hp=0), foe=slime())) == "foe"
    assert winner(BattleState(ada=ada(hp=0), foe=slime(hp=0))) == "foe"


def test_hp_ratio_helper():
    state = BattleState(ada=ada(hp=30), foe=slime(hp=35))
    assert state.hp_ratio("ada") == 0.5
    assert state.foe.hp_ratio == 0.25


def test_faster_side_moves_first_and_ties_are_a_coin_flip():
    assert first_mover(BattleState(ada=ada(), foe=slime()), random.Random(0)) == "ada"
    tie = BattleState(ada=ada(speed=3), foe=slime())
    results = {first_mover(tie, random.Random(seed)) for seed in range(20)}
    assert results == {"ada", "foe"}


def test_exhaustion_wears_off_when_that_side_acts_again():
    state = BattleState(ada=ada(), foe=slime(exhausted=True))
    state.scries_used = 2
    start_turn(state, "ada")
    assert state.foe.exhausted and state.scries_used == 0
    start_turn(state, "foe")
    assert not state.foe.exhausted
