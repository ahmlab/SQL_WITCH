"""The tutorial on screen (engine/tutorial_scene.py), driven by keys like a player."""

import pytest

pygame = pytest.importorskip("pygame")

from engine import render
from engine.grimoire import RIGHT_PAGE
from engine.scenes import GUIDE_BUTTON, TABLES_BUTTON, BattleScene, Game
from engine.tutorial_scene import (BUBBLE, DEMO_MS_PER_CHAR, READY_BUTTON, STRIP,
                                   TutorialScene)
from magic.tutorial import (DUMMY_CHARS, KEYS_CHARS, QUEST_CHARS, STRIP_CHARS, WRITE_CHARS,
                            load_script)


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


def press(game, k, mod=0):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))
    game.handle(pygame.event.Event(pygame.KEYUP, key=k, mod=mod))


def type_text(game, text):
    for char in text:
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))


def wait(game, ms):
    for _ in range(ms // 16 + 1):
        game.update(16)


def start(seed=2):
    game = Game(pygame.Surface((320, 180)), seed=seed)
    scene = TutorialScene(game)
    game.switch(scene)
    return game, scene


def to_task(game, scene, lesson=None):
    """ENTER through the talk (the demo types and casts by itself) until the player writes."""
    for _ in range(400):
        t = scene.tutorial
        if t.phase == "task" and (lesson is None or t.lesson["id"] == lesson):
            return
        if t.phase == "task":
            type_text(game, t.lesson["example"])
            press(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
        elif t.phase == "demo":
            wait(game, 200)
        else:
            press(game, pygame.K_RETURN)
        wait(game, 50)
    raise AssertionError(f"stuck in {scene.tutorial.phase}")


def drawn(scene):
    canvas = render.Canvas()
    scene.draw(canvas)
    return canvas


# ------------------------------------------------------------------ the whole tutorial

def test_a_player_finishes_the_tutorial_and_meets_the_slime_with_no_new_rune():
    game, scene = start()
    to_task(game, scene, "practice")
    press(game, pygame.K_F5)                                  # READY
    for _ in range(10):
        press(game, pygame.K_RETURN)
        wait(game, 50)
        if isinstance(game.scene, BattleScene) and game.scene.key == "slime":
            break
    assert isinstance(game.scene, BattleScene) and game.scene.key == "slime"
    assert game.scene.battle.state.ada.runes == set() and game.runes == set()
    assert scene.tutorial.passed == ["look", "columns", "read", "cast"]


def test_tab_and_ctrl_enter_alone_pass_lesson_one():
    game, scene = start()
    to_task(game, scene, "look")
    assert scene.editor.suggestion() == "SELECT * FROM enemies"
    press(game, pygame.K_TAB)
    press(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
    assert scene.tutorial.phase == "success"


def test_the_grimoire_types_the_demo_through_the_editor_then_casts_it():
    game, scene = start()
    press(game, pygame.K_RETURN)                              # past the opening
    while scene.tutorial.phase == "intro":
        press(game, pygame.K_RETURN)
    assert scene.tutorial.phase == "demo"
    wait(game, DEMO_MS_PER_CHAR * 6)
    assert "SELECT * FROM enemies".startswith(scene.editor.text) and scene.editor.text
    wait(game, DEMO_MS_PER_CHAR * 30)
    assert scene.tutorial.phase == "after"
    assert scene.grimoire.report.sql == "SELECT * FROM enemies"


def test_enter_finishes_the_demo_at_once():
    game, scene = start()
    while scene.tutorial.phase != "demo":
        press(game, pygame.K_RETURN)
    press(game, pygame.K_RETURN)
    wait(game, 100)
    assert scene.tutorial.phase == "after"


def test_the_page_is_cleared_for_the_player():
    game, scene = start()
    to_task(game, scene, "look")
    assert scene.editor.text == "" and scene.grimoire.report is None


# ------------------------------------------------------------------ progressive disclosure

def test_at_first_only_the_editor_the_page_and_the_instruction_show():
    game, scene = start()
    texts = drawn(scene).texts()
    for hidden in ("? GUIDE F3", "TABLES", "looks 3", "ADA", "TRAINING DUMMY", "F5 READY"):
        assert hidden not in texts
    assert "YOUR QUERY" in texts and "RESULT" in texts
    press(game, pygame.K_F4)
    press(game, pygame.K_F3)
    assert not scene.tables_open and not scene.guide.open     # hidden means unusable


def test_parts_appear_with_their_lessons_and_glow_once():
    game, scene = start()
    to_task(game, scene, "read")
    assert "ADA" in drawn(scene).texts()
    to_task(game, scene, "practice")
    texts = drawn(scene).texts()
    assert {"TABLES", "TRAINING DUMMY", "F5 READY"} <= set(texts)
    assert any(t.startswith("looks") for t in texts)
    assert "tables_button" in scene.pulses or scene.time > 0
    press(game, pygame.K_F4)
    assert scene.tables_open


def test_the_foes_book_never_shows_in_the_tutorial():
    game, scene = start()
    to_task(game, scene, "practice")
    assert not any(text.endswith("CAST:") for text in drawn(scene).texts())


# ------------------------------------------------------------------ pointing and coaching

def test_the_grimoire_circles_what_it_talks_about():
    game, scene = start()
    while scene.tutorial.phase != "after":
        press(game, pygame.K_RETURN)
        wait(game, 30)
    assert scene.tutorial.step.point == "row:0"
    rect = scene._part("row:0")
    assert rect is not None and RIGHT_PAGE.colliderect(rect)
    canvas = drawn(scene)
    edge = rect.inflate(4, 4)
    assert canvas.get_at(edge.topleft)[:3] in (render.GOLD, render.RED)


def test_enter_on_a_finished_query_teaches_ctrl_enter_without_changing_the_controls():
    game, scene = start()
    to_task(game, scene, "look")
    type_text(game, "SELECT * FROM enemies")
    press(game, pygame.K_RETURN)
    assert "\n" in scene.editor.text                          # ENTER still makes a new line
    assert "CTRL+ENTER" in scene.tutorial.strip().say
    press(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
    assert scene.tutorial.phase == "success"


def test_a_miscast_shows_the_games_message_and_what_to_type():
    game, scene = start()
    to_task(game, scene, "columns")
    type_text(game, "DROP TABLE enemies")
    press(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
    assert scene.grimoire.miscast and scene.grimoire.miscast.startswith("Ada:")
    assert scene.tutorial.strip().write == "SELECT name, weakness FROM enemies"
    assert scene.bubble                                       # the dummy has an opinion


def test_a_stuck_player_gets_the_faded_query_after_waiting():
    game, scene = start()
    to_task(game, scene, "cast")
    assert scene.editor.suggestion() == ""
    wait(game, load_script()["hints"]["idle_ms"][-1] + 100)
    assert scene.editor.suggestion() == "SELECT name FROM spells"


def test_ada_hp_never_moves_and_mp_is_full_at_every_task():
    game, scene = start()
    ada = scene.battle.state.ada
    for lesson in ("look", "columns", "read", "cast", "practice"):
        to_task(game, scene, lesson)
        assert ada.hp == ada.max_hp and ada.mp == ada.max_mp
        assert round(scene.bars["ada"][1]) == ada.max_mp      # and the bar shows it


# ------------------------------------------------------------------ leaving

def test_esc_asks_before_skipping_and_esc_again_stays():
    game, scene = start()
    press(game, pygame.K_ESCAPE)
    assert scene.confirm_skip and "Skip the tutorial?" in drawn(scene).texts()[-1]
    press(game, pygame.K_ESCAPE)
    assert not scene.confirm_skip and game.scene is scene
    press(game, pygame.K_ESCAPE)
    press(game, pygame.K_RETURN)
    assert isinstance(game.scene, BattleScene) and game.scene.key == "slime"
    assert scene.tutorial.records[-1]["result"] == "skipped"


def test_ready_works_only_in_free_practice_by_key_or_click():
    game, scene = start()
    to_task(game, scene, "look")
    press(game, pygame.K_F5)
    assert scene.tutorial.phase == "task"
    to_task(game, scene, "practice")
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=READY_BUTTON.center, button=1))
    assert scene.tutorial.phase == "ending"


def test_hidden_buttons_cannot_be_clicked():
    game, scene = start()
    to_task(game, scene, "look")
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=TABLES_BUTTON.center, button=1))
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=GUIDE_BUTTON.center, button=1))
    assert not scene.tables_open and not scene.guide.open


# ------------------------------------------------------------------ every line fits its box

def test_the_boxes_hold_the_characters_the_script_is_measured_against():
    f = render.font()
    assert f.width("x" * STRIP_CHARS) + 8 <= STRIP.width
    assert f.width("> " + "x" * WRITE_CHARS) + 8 <= STRIP.width
    assert f.width("[*] " + "x" * QUEST_CHARS) + 8 <= STRIP.width
    assert f.width("x" * DUMMY_CHARS) + 8 <= BUBBLE.width
    assert f.width("x" * KEYS_CHARS) + 8 <= 320
    assert STRIP.right < 202 and BUBBLE.x > STRIP.right       # side by side, never on top


def test_every_screen_of_the_tutorial_draws_without_text_off_the_canvas():
    game, scene = start()
    seen = 0
    for _ in range(300):
        canvas = drawn(scene)
        for op in canvas.ops:
            if op[0] == "text" and op[-1] == canvas.get_rect():   # clipped text is cut on purpose
                assert 0 <= op[2] and op[2] + render.font().width(op[1]) <= 320, op[1]
        seen += 1
        t = scene.tutorial
        if t.practising and t.phase == "task":
            break
        if t.phase == "task":
            type_text(game, t.lesson["example"])
            press(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
        elif t.phase == "demo":
            wait(game, 300)
        else:
            press(game, pygame.K_RETURN)
        wait(game, 30)
    assert seen > 15
