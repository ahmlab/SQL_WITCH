import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import sqlglot

from ai.base import RandomBrain
from ai.fsm import SLIME_INTENTS, TRANSITIONS, SlimeBrain, slime_legal_intents
from ai.styles import SLIME_RUNES, book_uses, render_slime
from magic import guard
from magic.cast import load_state, resolve
from magic.db import build_db


def fresh_state(seed=0):
    conn = build_db()
    state = load_state(conn, seed=seed)
    state.foe.runes = set(SLIME_RUNES)
    return conn, state


def run_brain(brain, seed, turns=30):
    _, state = fresh_state(seed)
    rng = random.Random(seed)
    return [brain.decide(state, rng).action for _ in range(turns)]


# ------------------------------------------------------------------ the brains

@pytest.mark.parametrize("seed", range(30))
def test_the_fsm_only_returns_legal_intents(seed):
    _, state = fresh_state(seed)
    rng, brain = random.Random(seed), SlimeBrain()
    legal = slime_legal_intents(state)
    for _ in range(40):
        state.foe.hp = rng.randint(1, state.foe.max_hp)     # wander through the override too
        assert brain.decide(state, rng) in legal


def test_same_seed_same_sequence_and_different_seeds_differ():
    assert run_brain(SlimeBrain(), 7) == run_brain(SlimeBrain(), 7)
    sequences = {tuple(run_brain(SlimeBrain(), seed)) for seed in range(10)}
    assert len(sequences) > 1


def test_overcast_is_always_followed_by_exhausted():
    _, state = fresh_state()
    for seed in range(50):
        brain = SlimeBrain(start="overcast")
        assert brain.decide(state, random.Random(seed)).action == "exhausted"


def test_transition_frequencies_match_the_table():
    _, state = fresh_state()
    rng = random.Random(123)
    counts = Counter()
    for _ in range(5000):
        brain = SlimeBrain(start="wobble")
        counts[brain.decide(state, rng).action] += 1
    assert abs(counts["overcast"] / 5000 - 0.7) < 0.03


def test_a_desperate_slime_is_always_careful():
    _, state = fresh_state()
    state.foe.hp = 41                         # below 30% of 140
    for start in TRANSITIONS:
        brain = SlimeBrain(start=start)
        assert brain.decide(state, random.Random(0)).action == "careful"
        assert brain.explain()["override"] is True


def test_explain_shows_the_state_and_the_probabilities():
    _, state = fresh_state()
    brain = SlimeBrain()
    brain.decide(state, random.Random(0))
    why = brain.explain()
    assert why["previous"] == "wobble"
    assert why["probabilities"] == {"overcast": 0.7, "wobble": 0.3}
    assert why["state"] in ("overcast", "wobble")


def test_the_random_baseline_is_legal_and_roughly_uniform():
    _, state = fresh_state()
    brain, rng = RandomBrain(slime_legal_intents), random.Random(5)
    counts = Counter(brain.decide(state, rng).action for _ in range(4000))
    assert set(counts) == set(SLIME_INTENTS)
    assert all(abs(n / 4000 - 0.25) < 0.03 for n in counts.values())
    assert brain.explain()["probability"] == 0.25


# ------------------------------------------------------------------ the style

ALL_INTENTS = list(SLIME_INTENTS.values())


@pytest.mark.parametrize("intent", ALL_INTENTS, ids=lambda i: i.action)
@pytest.mark.parametrize("turn", [1, 2, 3, 4])
def test_every_slime_query_passes_the_rune_gate(intent, turn):
    _, state = fresh_state()
    sql = render_slime(intent, state, turn)
    assert guard.inspect(sql, SLIME_RUNES) <= SLIME_RUNES


def test_careful_adds_limit_two():
    _, state = fresh_state()
    assert render_slime(SLIME_INTENTS["careful"], state, 1) == \
        "SELECT * FROM foe_spells WHERE foe_id = 1 LIMIT 2"
    assert render_slime(SLIME_INTENTS["overcast"], state, 1) == \
        "SELECT * FROM foe_spells WHERE foe_id = 1"


def test_teaching_guarantee_forces_limit_by_the_third_turn():
    _, state = fresh_state()
    wobble = SLIME_INTENTS["wobble"]
    state.foe_book = [render_slime(wobble, state, 1), render_slime(wobble, state, 2)]
    third = render_slime(wobble, state, 3)
    assert "LIMIT" in third and "foe_spells" in third


def test_no_forcing_once_limit_has_been_shown():
    _, state = fresh_state()
    state.foe_book = [render_slime(SLIME_INTENTS["careful"], state, 1)]
    assert book_uses(state, "LIMIT")
    assert "LIMIT" not in render_slime(SLIME_INTENTS["overcast"], state, 3)


def test_the_slime_attack_lands_through_the_real_pipeline():
    conn, state = fresh_state()
    sql = render_slime(SLIME_INTENTS["careful"], state, 1)
    report = resolve(conn, state, sql, "foe", random.Random(0))
    assert [c.spell for c in report.casts] == ["Goo Spit", "Sticky Slap"]
    assert state.foe.mp == 15 and state.ada.hp < 60


@pytest.mark.parametrize("intent", ALL_INTENTS, ids=lambda i: i.action)
def test_mutation_an_empty_filter_makes_the_turn_do_nothing(intent):
    """The core claim: the SQL is not decoration. Break the query and the Slime does nothing,
    whatever its brain intended."""
    conn, state = fresh_state()
    sql = render_slime(intent, state, 1)
    broken = sqlglot.parse_one(sql, read="sqlite").where("1 = 0").sql(dialect="sqlite")
    assert "AND 1 = 0" in broken
    report = resolve(conn, state, broken, "foe", random.Random(0))
    assert report.rows == [] and report.casts == []
    assert (state.ada.hp, state.foe.mp) == (60, 20)


def test_wobble_and_exhausted_cast_nothing():
    conn, state = fresh_state()
    for action in ("wobble", "exhausted"):
        sql = render_slime(SLIME_INTENTS[action], state, 1)
        report = resolve(conn, state, sql, "foe", random.Random(0))
        assert report.scry and report.casts == [] and state.foe.mp == 20


def test_magic_and_ai_never_import_pygame():
    code = ("import sys, magic.rules, magic.cast, ai.base, ai.fsm, ai.styles; "
            "sys.exit('pygame' in sys.modules)")
    root = Path(__file__).resolve().parent.parent
    assert subprocess.run([sys.executable, "-c", code], cwd=root).returncode == 0
