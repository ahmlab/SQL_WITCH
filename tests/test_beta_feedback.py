"""The changes asked for after the beta test: shaded casts, sideways scrolling, the Knight's
text, guided typing, the TABLES button and one theme per guardian."""

import json
import re

import pytest

pygame = pytest.importorskip("pygame")

from engine import render
from engine.grimoire import (RIGHT_PAGE, SCROLL_RIGHT, SHADE_CAST, SHADE_DEFLECTED, Grimoire,
                             row_shades)
from engine.scenes import TABLES_BUTTON, BattleScene, Game
from engine.textinput import QueryEditor, next_step
from magic.battle import Battle
from magic.db import DATA_DIR


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


def to_battle(start="slime", seed=2):
    game = Game(pygame.Surface((320, 180)), seed=seed, start=start)
    press(game, pygame.K_RETURN)
    press(game, pygame.K_ESCAPE)
    scene = game.scene
    for _ in range(600):
        if scene.phase == "input":
            break
        game.update(16)
    return game, scene


# ------------------------------------------------------------------ 1. the spells that cast are shaded

def test_rows_that_cast_are_shaded_and_deflected_ones_differently():
    battle = Battle(seed=1, foe_opens=False)
    report = battle.ada_cast("SELECT name FROM spells")
    assert row_shades(report) == {0: SHADE_CAST, 1: SHADE_CAST, 2: SHADE_CAST, 3: SHADE_CAST}
    knight = Battle(seed=1, guardian="knight")
    knight.foe_act()                                         # raises his Ward of Relevance
    bounced = knight.ada_cast("SELECT name FROM spells LIMIT 1")   # Ember: not super-effective
    assert row_shades(bounced) == {0: SHADE_DEFLECTED}


def test_the_shade_is_drawn_behind_the_row():
    battle = Battle(seed=1, ada_runes={"LIMIT"}, foe_opens=False)
    grimoire = Grimoire(QueryEditor())
    grimoire.show_result(battle.ada_cast("SELECT name FROM spells LIMIT 1"), 0, 3)
    canvas = render.Canvas()
    grimoire.draw(canvas, now=5000, focused=False)
    row_y = RIGHT_PAGE.y + 8 + 8 + 4                         # inside the first row's band
    band = {canvas.get_at((x, row_y))[:3] for x in range(RIGHT_PAGE.x, RIGHT_PAGE.right)}
    assert SHADE_CAST in band


# ------------------------------------------------------------------ 2. sideways scrolling

def scry_enemies():
    battle = Battle(seed=1, foe_opens=False)
    grimoire = Grimoire(QueryEditor())
    grimoire.show_result(battle.ada_cast("SELECT * FROM enemies"), 0, 3)
    return battle, grimoire


def test_hidden_columns_can_be_scrolled_into_view_and_back():
    battle, grimoire = scry_enemies()
    report = grimoire.report
    assert not grimoire.can_scroll(-1) and grimoire.can_scroll(1)
    while grimoire.scroll(1):
        pass
    canvas = render.Canvas()
    grimoire.draw(canvas, now=5000, focused=False)
    visible = [op for op in canvas.ops if op[0] == "text" and op[1] == "weakness"
               and RIGHT_PAGE.x <= op[2] < RIGHT_PAGE.right]
    assert visible                                           # the weakness column is readable
    while grimoire.scroll(-1):
        pass
    assert grimoire.scroll_col == 0
    assert battle.state.ada.mp == 30 and report.scry         # looking costs nothing


def test_a_new_result_starts_unscrolled():
    battle, grimoire = scry_enemies()
    grimoire.scroll(1)
    grimoire.show_result(battle.ada_cast("SELECT * FROM witch"), 0, 2)
    assert grimoire.scroll_col == 0


def test_shift_arrows_wheel_and_arrow_clicks_scroll_in_battle():
    game, scene = to_battle()
    type_text(game, "SELECT * FROM enemies")
    press(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
    press(game, pygame.K_RIGHT, pygame.KMOD_LSHIFT)
    assert scene.grimoire.scroll_col == 1
    game.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1))
    assert scene.grimoire.scroll_col == 2
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=SCROLL_RIGHT.center, button=1))
    assert scene.grimoire.scroll_col == 3
    press(game, pygame.K_LEFT, pygame.KMOD_LSHIFT)
    assert scene.grimoire.scroll_col == 2
    assert scene.editor.text == ""                           # the arrows did not reach the editor


# ------------------------------------------------------------------ 3. the Knight's text

def test_the_knights_lines_are_plain_and_consistent_with_his_ward():
    dialogue = json.loads((DATA_DIR / "dialogue.json").read_text())
    text = " ".join(line["text"] for line in dialogue["knight_intro"])
    text += " ".join(dialogue["knight_victory"] + dialogue["knight_defeat"])
    for archaic in ("thou", "canst", "thy", "thee"):
        assert not re.search(rf"\b{archaic}\b", text.lower())
    assert "lets you through" not in text                     # his ward never lets spells through
    assert "SELECT * FROM enemies" in text and "WHERE" in text


# ------------------------------------------------------------------ 4. guided typing

@pytest.mark.parametrize("typed, runes, expected", [
    ("", set(), ("SELECT", "")),
    ("SELECT ", set(), ("name", "")),
    ("SELECT name ", set(), ("FROM spells", "")),
    ("SELECT * ", set(), ("FROM enemies", "")),
    ("SELECT name FROM spells ", set(), ("", "CTRL+ENTER casts")),
    ("SELECT name FROM spells ", {"LIMIT"}, ("LIMIT 1", "")),
    ("SELECT name FROM spells ", {"LIMIT", "WHERE"}, ("WHERE element =", "")),
    ("SELECT name FROM spells LIMIT ", set(), ("", "LIMIT is a rune you have not learned yet")),
    ("select name ", set(), ("from spells", "")),
])
def test_the_next_piece_of_a_query_is_offered(typed, runes, expected):
    assert next_step(typed, runes) == expected


def test_the_weakness_is_only_offered_once_she_has_looked():
    typed = "SELECT name FROM spells WHERE element = "
    assert next_step(typed, {"WHERE"})[0] == ""
    assert next_step(typed, {"WHERE"}, weakness="Storm")[0] == "'Storm'"


def test_select_then_tab_then_tab_writes_a_whole_query():
    game, scene = to_battle()
    type_text(game, "SELECT")
    assert scene.editor.suggestion() == " name"               # right after the keyword
    press(game, pygame.K_TAB)
    assert scene.editor.text == "SELECT name"
    press(game, pygame.K_TAB)
    assert scene.editor.text == "SELECT name FROM spells"
    assert scene.editor.hint() == "CTRL+ENTER casts"


def test_an_empty_page_suggests_select_and_the_ghost_is_shaded():
    editor = QueryEditor()
    assert editor.suggestion() == "SELECT"
    canvas = render.Canvas()
    editor.draw(canvas, (2, 2), time_ms=0)
    assert canvas.get_at((4, 4))[:3] == render.PARCHMENT     # a band behind the faded text


def test_looking_at_the_knight_teaches_the_editor_his_weakness():
    game, scene = to_battle("knight")
    assert scene.editor.known_weakness is None
    type_text(game, "SELECT * FROM enemies")
    press(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
    assert scene.editor.known_weakness == "Storm"


# ------------------------------------------------------------------ 5. the TABLES button

def test_the_tables_button_lists_every_table_and_writes_a_name():
    game, scene = to_battle()
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=TABLES_BUTTON.center, button=1))
    assert scene.tables_open
    canvas = render.Canvas()
    scene.draw(canvas)
    names = {table for _, table in scene.table_rows}
    assert {"spells", "enemies", "items", "witch", "type_chart", "foe_spells"} <= names
    assert any(op[0] == "text" and "weakness" in op[1] for op in canvas.ops)  # columns shown
    type_text(game, "SELECT * FROM ")                        # typing still works while open
    rect = next(r for r, table in scene.table_rows if table == "enemies")
    game.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1))
    assert scene.editor.text == "SELECT * FROM enemies" and not scene.tables_open


def test_f4_and_escape_open_and_close_the_tables():
    game, scene = to_battle()
    press(game, pygame.K_F4)
    assert scene.tables_open
    press(game, pygame.K_ESCAPE)
    assert not scene.tables_open


# ------------------------------------------------------------------ 6. one theme per guardian

@pytest.mark.parametrize("guardian", ["slime", "knight"])
def test_each_guardian_plays_its_own_theme(guardian):
    game, scene = to_battle(guardian)
    assert game.audio.music == guardian
    themes = json.loads((DATA_DIR.parent / "assets" / "audio" / "sounds.json").read_text())["music"]
    assert themes["slime"]["file"] != themes["knight"]["file"]
