"""The Hearth (prompt 08 §2): rest by the data, letters on story flags, backups restorable."""

import pytest

from magic.fatigue import TUNING, Fatigue
from magic.guard import Miscast
from magic.hearth import DATA, Hearth, restore_backup
from save.state import GameState


def hearth(fatigue=0.8, beaten=("slime",), **state):
    s = GameState(beaten=list(beaten), **state)
    return Hearth(s, Fatigue(fatigue))


def test_sleep_resets_fatigue():
    h = hearth(0.8)
    h.sleep()
    assert h.fatigue.value == 0.0


def test_a_meal_takes_off_its_recipes_rest_and_uses_the_pantry():
    h = hearth(0.8)
    oats = h.pantry()["Oats"]
    meal = h.cook("SELECT name, rest FROM recipes WHERE needs = 'Oats'")
    assert meal.name == "Plain Porridge"
    assert h.fatigue.value == pytest.approx(0.8 - 0.15)
    assert h.pantry()["Oats"] == oats - 1


def test_two_different_queries_cook_the_same_meal():
    for sql in ("SELECT name FROM recipes WHERE rest > 0.3",
                "SELECT name FROM recipes ORDER BY rest DESC LIMIT 1"):
        assert hearth().cook(sql).name == "Wenna's Pie"


def test_a_meal_the_pantry_cannot_make_is_refused_and_changes_nothing():
    h = hearth(0.8)
    with pytest.raises(Miscast):
        h.cook("SELECT name FROM recipes WHERE needs = 'Fish'")
    assert h.fatigue.value == 0.8 and not h.ate


def test_a_look_at_the_recipes_is_not_a_meal():
    h = hearth(0.8)
    meal = h.cook("SELECT needs, rest FROM recipes")
    assert meal.name == "" and h.fatigue.value == 0.8


def test_one_supper_a_night():
    h = hearth(0.8)
    h.cook("SELECT name FROM recipes WHERE needs = 'Oats'")
    with pytest.raises(Miscast):
        h.cook("SELECT name FROM recipes WHERE needs = 'Barley'")


def test_the_kitchen_refuses_writes():
    with pytest.raises(Miscast):
        hearth().cook("DELETE FROM pantry")


def test_letters_arrive_on_the_right_story_flags():
    assert hearth(beaten=()).letters_due() == []
    assert hearth(beaten=("slime",)).letters_due() == ["letter_1"]
    assert hearth(beaten=("slime", "knight")).letters_due() == ["letter_1", "letter_2"]


def test_reading_a_letter_rests_a_little_and_gives_focus():
    h = hearth(0.5)
    h.read_letter("letter_1")
    assert h.fatigue.value == pytest.approx(0.5 - TUNING["fall"]["letter"])
    assert h.fatigue.focused
    assert h.letters_due() == []
    with pytest.raises(ValueError):
        h.read_letter("letter_2")                      # the Keep is not beaten yet


def test_leaving_without_sleep_is_allowed_counted_and_burns_marta_out():
    h = hearth(0.3)
    h.arrive()
    h.leave()
    assert h.story["skipped_sleeps"] == 1 and not h.story["burnout"]
    assert h.fatigue.value == pytest.approx(0.3 + TUNING["rise"]["skipped_sleep"])
    h.arrive()
    assert h.leave()["burnout"] and h.story["burnout"]
    h.arrive()
    h.sleep()
    h.leave()
    assert h.story["skipped_sleeps"] == 0 and not h.story["burnout"]


def test_companions_join_by_story_progress():
    assert hearth(beaten=()).companions() == []
    assert hearth(beaten=("slime",)).companions() == ["marta"]


def test_the_world_backup_is_restorable():
    h = hearth(inventory={"Ether": 1, "Rust Salts": 2}, scrolls={"ember": "SELECT name FROM spells LIMIT 1"})
    h.scrolls = dict(h.state.scrolls)
    name = h.backup("before the clock")
    conn = restore_backup(h.state.backups[name])
    assert conn.execute("SELECT name, qty FROM items ORDER BY name").fetchall() == \
        [("Ether", 1), ("Rust Salts", 2)]
    assert conn.execute("SELECT * FROM scroll_ember").fetchall()
    original = h.world()
    for table in ("witch", "spells", "items", "enemies"):
        assert conn.execute(f"SELECT * FROM {table}").fetchall() == \
            original.execute(f"SELECT * FROM {table}").fetchall()


def test_the_backup_shelf_keeps_a_few_and_the_save_keeps_them():
    h = hearth()
    for i in range(DATA["backups"] + 2):
        h.backup(f"b{i}")
    assert len(h.state.backups) == DATA["backups"]
    back = GameState.from_dict(h.state.to_dict())
    assert back.backups == h.state.backups


def test_every_hearth_node_and_letter_the_data_names_exists():
    from story.script import get
    nodes = {k.split(".")[2] for k in get("hearth").keys()}
    letters = {k.split(".")[2] for k in get("letters").keys()}
    for c in DATA["companions"]:
        assert c["talk"] in nodes and c["leave"] in nodes
    assert DATA["arrival"] in nodes and DATA["woke"] in nodes
    assert {l["id"] for l in DATA["letters"]} <= letters
