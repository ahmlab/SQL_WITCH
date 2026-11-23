import math
import random

import pytest

pygame = pytest.importorskip("pygame")

from engine import render, scenery
from engine.guide import PAGES, Guide, load_guide
from engine.scenes import GUIDE_BUTTON, BattleScene, Game
from engine.textinput import layout
from magic import guard
from magic.battle import Battle
from magic.cast import resolve


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


def press(game, k, mod=0):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))
    game.handle(pygame.event.Event(pygame.KEYUP, key=k, mod=mod))


def to_battle(start="slime"):
    game = Game(pygame.Surface((320, 180)), seed=2, start=start)
    press(game, pygame.K_RETURN)
    press(game, pygame.K_ESCAPE)
    scene = game.scene
    for _ in range(600):
        if scene.phase == "input":
            break
        game.update(16)
    return game, scene


# ------------------------------------------------------------------ the examples are honest

@pytest.mark.parametrize("example", load_guide()["examples"], ids=lambda e: e["sql"])
def test_every_example_is_valid_and_its_label_is_true(example):
    """A LOOK must really be a free scry and a CAST must really cast, with only the runes
    the example says it needs."""
    battle = Battle(seed=1, guardian="slime", ada_runes=set(example["needs"]), level=2)
    state = battle.state
    guard.inspect(example["sql"], state.ada.runes)
    report = resolve(battle.conn, state, example["sql"], "ada", random.Random(0))
    assert report.scry == (example["kind"] == "look")


def test_examples_unlock_with_the_runes():
    guide = Guide(Battle(seed=1).conn, set())
    ready = {e["sql"] for e in guide.examples() if e["ready"]}
    assert "SELECT * FROM enemies" in ready
    assert "SELECT name FROM spells LIMIT 1" not in ready
    guide.runes.add("LIMIT")
    assert "SELECT name FROM spells LIMIT 1" in {e["sql"] for e in guide.examples() if e["ready"]}


# ------------------------------------------------------------------ using it in battle

def test_f3_opens_the_guide_and_it_takes_the_keyboard():
    game, scene = to_battle()
    press(game, pygame.K_F3)
    assert scene.guide.open and game.guide_seen
    game.handle(pygame.event.Event(pygame.TEXTINPUT, text="x"))
    assert scene.editor.text == ""                         # typing goes nowhere while open
    for i in range(len(PAGES)):
        press(game, pygame.K_1 + i)
        assert scene.guide.page == i
        game.draw()                                        # every page draws
    press(game, pygame.K_ESCAPE)
    assert not scene.guide.open


def test_enter_writes_the_chosen_example_on_the_page():
    game, scene = to_battle()
    press(game, pygame.K_F3)
    press(game, pygame.K_3)
    press(game, pygame.K_DOWN)                             # the second example
    press(game, pygame.K_RETURN)
    assert not scene.guide.open
    assert scene.editor.text == layout("SELECT element, power, mp_cost FROM spells")


def test_a_locked_example_cannot_be_written():
    game, scene = to_battle()
    press(game, pygame.K_F3)
    press(game, pygame.K_3)
    examples = scene.guide.examples()
    scene.guide.choice = next(i for i, e in enumerate(examples) if not e["ready"])
    press(game, pygame.K_RETURN)
    assert scene.guide.open and scene.editor.text == ""


def test_the_guide_button_can_be_clicked():
    game, scene = to_battle()
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=GUIDE_BUTTON.center, button=1))
    assert scene.guide.open


def test_a_click_in_the_window_lands_on_the_right_game_pixel():
    screen = render.Screen(scale=3)
    assert screen.to_logical((GUIDE_BUTTON.centerx * 3 + 1, GUIDE_BUTTON.centery * 3 + 2)) == \
        GUIDE_BUTTON.center


def test_holding_f3_does_not_flicker_the_guide():
    game, scene = to_battle()
    for _ in range(5):                                     # held: one press, many repeats
        game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F3, mod=0))
    assert scene.guide.open


def test_the_guide_works_against_the_knight_too():
    game, scene = to_battle("knight")
    press(game, pygame.K_F3)
    press(game, pygame.K_3)
    ready = [e for e in scene.guide.examples() if e["ready"]]
    assert any("WHERE" in e["sql"] for e in ready)        # he taught WHERE in his first move
    game.draw()


# ------------------------------------------------------------------ laying a query out

@pytest.mark.parametrize("example", load_guide()["examples"], ids=lambda e: e["sql"])
def test_layout_never_cuts_a_word_and_fits_the_page(example):
    text = layout(example["sql"], 36)
    assert all(len(line) <= 36 for line in text.split("\n"))
    assert text.split() == example["sql"].split()


def test_layout_breaks_before_clauses():
    assert layout("SELECT name FROM spells WHERE element = 'Fire' AND power > 30 LIMIT 1") == \
        "SELECT name FROM spells\nWHERE element = 'Fire'\n  AND power > 30 LIMIT 1"


# ------------------------------------------------------------------ Ada falls asleep in one piece

@pytest.mark.parametrize("drowsy", [x / 10 for x in range(31)])
def test_adas_head_stays_on_her_shoulders_as_she_falls_asleep(drowsy):
    for t in (0, 700, 1400):
        hip, shoulder, head = scenery.ada_pose(drowsy, t)
        assert hip == scenery.HIP                                   # she stays in her chair
        assert math.dist(hip, shoulder) == pytest.approx(scenery.TORSO)
        assert math.dist(shoulder, head) == pytest.approx(scenery.NECK)
        assert head[1] + 7 <= 92.5                                  # never sinks into the desk


def test_she_leans_further_the_sleepier_she_is():
    leans = [scenery.ada_pose(d, 0)[2][0] for d in (0, 1, 2, 3)]
    assert leans == sorted(leans) and leans[-1] - leans[0] > 15
