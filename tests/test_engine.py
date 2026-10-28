import pytest

pygame = pytest.importorskip("pygame")

from engine import render
from engine.textinput import (QueryEditor, colour_styles, locked_words, schema_tables,
                              schema_words)
from magic.cast import PAGE_WIDTH
from magic.db import build_db


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    yield
    pygame.quit()


def text_event(text):
    return pygame.event.Event(pygame.TEXTINPUT, text=text)


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod)


def typed(editor, text):
    for char in text:
        editor.handle_event(key(pygame.K_RETURN) if char == "\n" else text_event(char))
    return editor


# ------------------------------------------------------------------ render

@pytest.mark.parametrize("window, expected", [
    ((1280, 720), (4, (0, 0))),
    ((1920, 1080), (6, (0, 0))),
    ((1000, 700), (3, (20, 80))),
    ((200, 100), (1, (-60, -40))),
])
def test_integer_scaling_with_letterbox(window, expected):
    assert render.fit(window) == expected


def test_the_palette_has_32_distinct_colours():
    assert len(set(render.PALETTE)) == 32


def test_every_glyph_fits_its_cell():
    for char, rows in render._GLYPHS.items():
        assert len(rows) <= render.GLYPH_H, char
        assert all(len(row) == render.GLYPH_W for row in rows), char


def test_a_full_page_line_fits_the_right_page():
    # The right page is 146 px wide (design doc 6.4): PAGE_WIDTH characters must fit.
    assert render.font().width("x" * PAGE_WIDTH) <= 146


def test_text_is_drawn_on_whole_pixels():
    surface = pygame.Surface((40, 10))
    surface.fill(render.CREAM)
    render.font().draw(surface, "I", (1.4, 2.6), render.INK)
    assert surface.get_at((1, 3))[:3] == render.INK        # (1.4, 2.6) -> (1, 3)


def test_the_screen_presents_without_a_real_display():
    screen = render.Screen(scale=2)
    screen.canvas.fill(render.VIOLET)
    screen.present()
    assert screen.window.get_size() == (640, 360)


# ------------------------------------------------------------------ the editor

def test_typing_backspace_and_newlines():
    editor = typed(QueryEditor(), "SELECT name\nFROM spells")
    assert editor.text == "SELECT name\nFROM spells"
    for _ in range(len("FROM spells") + 1):
        editor.handle_event(key(pygame.K_BACKSPACE))
    assert editor.text == "SELECT name"


def test_cursor_moves_and_inserts_in_the_middle():
    editor = typed(QueryEditor(), "SELECT * spells")
    for _ in range(6):
        editor.handle_event(key(pygame.K_LEFT))
    typed(editor, "FROM ")
    assert editor.text == "SELECT * FROM spells"
    editor.handle_event(key(pygame.K_HOME))
    editor.handle_event(key(pygame.K_DELETE))
    assert editor.text == "ELECT * FROM spells"


def test_tabs_and_control_characters_are_not_typed():
    assert typed(QueryEditor(), "a\tb\x07").text == "ab"


def test_enter_is_a_newline_and_ctrl_enter_casts():
    editor = typed(QueryEditor(), "SELECT name FROM spells")
    assert editor.handle_event(key(pygame.K_RETURN)) is None
    sql = editor.handle_event(key(pygame.K_RETURN, pygame.KMOD_LCTRL))
    assert sql == "SELECT name FROM spells"
    assert editor.text == "" and editor.history == [sql]


def test_casting_an_empty_page_does_nothing():
    assert QueryEditor().handle_event(key(pygame.K_RETURN, pygame.KMOD_CTRL)) is None


def test_up_and_down_walk_the_history_and_keep_the_draft():
    editor = QueryEditor()
    for sql in ("SELECT * FROM enemies", "SELECT name FROM spells"):
        typed(editor, sql)
        editor.submit()
    typed(editor, "SEL")
    editor.handle_event(key(pygame.K_UP))
    assert editor.text == "SELECT name FROM spells"
    editor.handle_event(key(pygame.K_UP))
    assert editor.text == "SELECT * FROM enemies"
    editor.handle_event(key(pygame.K_DOWN))
    editor.handle_event(key(pygame.K_DOWN))
    assert editor.text == "SEL"


def test_up_moves_between_lines_before_touching_history():
    editor = QueryEditor()
    typed(editor, "SELECT 1")
    editor.submit()
    typed(editor, "SELECT name\nFROM spells")
    editor.handle_event(key(pygame.K_UP))
    assert editor.row == 0 and editor.text == "SELECT name\nFROM spells"


def test_tab_completes_schema_names_and_cycles():
    conn = build_db()
    names, tables = schema_words(conn), schema_tables(conn)
    assert {"spells", "foe_spells", "mp_cost", "type_chart"} <= set(names)
    editor = typed(QueryEditor(names=names, tables=tables), "SELECT * FROM spe")
    editor.handle_event(key(pygame.K_TAB))
    assert editor.text == "SELECT * FROM spells"
    editor = typed(QueryEditor(names=names, tables=tables), "SELECT m")
    editor.handle_event(key(pygame.K_TAB))
    first = editor.text
    editor.handle_event(key(pygame.K_TAB))
    assert editor.text != first and editor.text.startswith("SELECT m")


def test_tab_keeps_the_players_case_for_keywords():
    lower = typed(QueryEditor(), "sel")
    lower.handle_event(key(pygame.K_TAB))
    upper = typed(QueryEditor(), "SEL")
    upper.handle_event(key(pygame.K_TAB))
    assert (lower.text, upper.text) == ("select", "SELECT")


def test_long_lines_wrap_at_the_page_width():
    editor = typed(QueryEditor(columns=10), "SELECT name, element FROM spells")
    lines, cursor = editor.visual_lines()
    assert [text for _, _, text in lines] == ["SELECT nam", "e, element", " FROM spel", "ls"]
    assert cursor == (3, 2)


# ------------------------------------------------------------------ colouring

def test_locked_runes_are_marked_and_unlocked_ones_are_not():
    sql = "SELECT name FROM spells LIMIT 1"
    start = sql.index("LIMIT")
    locked = colour_styles(sql, locked_words(set()), set())
    assert set(locked[start:start + 5]) == {"locked"}
    assert locked[0] == "keyword"
    free = colour_styles(sql, locked_words({"LIMIT"}), set())
    assert set(free[start:start + 5]) == {"keyword"}


def test_strings_numbers_and_names_get_their_colours():
    sql = "SELECT name FROM spells WHERE element = 'Fire' AND power > 15"
    styles = colour_styles(sql, set(), {"name", "spells", "element", "power"})
    assert styles[sql.index("'Fire'")] == "string"
    assert styles[sql.index("15")] == "number"
    assert styles[sql.index("spells")] == "name"


def test_a_half_typed_string_does_not_break_the_colours():
    styles = colour_styles("SELECT name FROM spells WHERE element = 'Fi", set(), set())
    assert styles[-1] == "string"


def test_the_editor_draws_without_crashing():
    surface = pygame.Surface((150, 64))
    editor = typed(QueryEditor(names=["spells"], unlocked=set()),
                   "SELECT name FROM spells WHERE power > 15 LIMIT 1")
    editor.draw(surface, (2, 2), time_ms=0)
