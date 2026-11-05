"""A smaller guardian's book, a darker glade, a readable title and a sandbox that never crashes."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pygame = pytest.importorskip("pygame")

from ai.base import Intent
from ai.styles import KNIGHT_FILTERS, render_knight
from engine import render, scenes
from engine.grimoire import FOE_BOOK, FOE_LINE_CHARS, draw_foe_book, wrap
from engine.scenes import ADA_FEET, Game, TitleScene

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


def luminance(rgb):
    r, g, b = rgb[:3]
    return 0.3 * r + 0.59 * g + 0.11 * b


# ------------------------------------------------------------------ the guardian's book

def test_the_foes_book_is_smaller_than_before_and_in_small_print():
    canvas = render.Canvas()
    sql = "SELECT * FROM foe_spells WHERE foe_id = 1"
    draw_foe_book(canvas, "Asterisk Slime", sql, None, None, 0)
    assert FOE_BOOK.width * FOE_BOOK.height < 0.75 * 152 * 33   # the old box was 152 x 33
    assert FOE_BOOK.bottom < ADA_FEET[1] - 41                    # clear of Ada (41 px tall)
    small = [op for op in canvas.ops if op[0] == "small"]
    assert small and all(op[0] != "text" for op in canvas.ops)
    for _, text, x, *_ in small:                                # every line fits inside the box
        assert x + render.font().width(text, small=True) <= FOE_BOOK.right - 2


def test_the_knights_longest_query_still_fits_three_lines():
    state = SimpleNamespace(foe_id=2)
    for action in [*KNIGHT_FILTERS, "rest"]:
        sql = render_knight(Intent(action=action), state, 1)
        assert len(wrap(sql, FOE_LINE_CHARS)) <= 3, sql


@pytest.mark.parametrize("k", range(2, 9))
def test_small_print_keeps_the_height_of_normal_text_and_fits_its_cell(k):
    dot_x, dot_y, bold = render.small_print_dots(k)
    assert 5 * dot_x + bold <= render.SMALL_ADVANCE * k - 1      # a gap between letters
    assert render.FINE_H * dot_y <= render.SMALL_LINE_H * k       # descenders stay in the line
    assert dot_y >= render.fine_pixel(k)                          # as tall as normal text


def test_small_print_is_drawn_on_the_text_layer():
    canvas = render.Canvas()
    render.font().draw(canvas, "WHERE", (4, 4), render.INK, small=True)
    assert canvas.texts() == ["WHERE"]
    frame = pygame.Surface((320 * 3, 180 * 3))
    frame.fill(render.CREAM)
    render.draw_text_layer(frame, canvas.ops, 3)
    inked = sum(frame.get_at((x, y))[:3] == render.INK for x in range(12, 12 + 15 * 3)
                for y in range(12, 12 + 18))
    assert inked > 60


# ------------------------------------------------------------------ the glade

def test_the_glade_grass_is_darker_than_the_slime():
    assert luminance(scenes.GRASS_FIELD) < luminance(render.GRASS) - 40
    assert luminance(scenes.GROUND_SHADOW) <= luminance(scenes.GRASS_FIELD)
    canvas = pygame.Surface((320, 180))
    scenes.draw_backdrop(canvas)
    assert canvas.get_at((10, 100))[:3] == scenes.GRASS_FIELD


# ------------------------------------------------------------------ the title

def big_letter(char):
    surface = pygame.Surface((40, 40))
    surface.fill(render.INK)
    render.font().draw_big(surface, char, (0, 0), render.WHITE, dot=3)
    return {(x, y) for x in range(40) for y in range(40) if surface.get_at((x, y))[:3] == render.WHITE}


def test_the_titles_w_no_longer_looks_like_an_h():
    w, h = big_letter("W"), big_letter("H")
    assert len(w ^ h) // 9 >= 8           # 8 dots (3x3 blocks) apart; the old 3x5 letters: 1
    assert len(big_letter("Q") ^ big_letter("O")) > 0


def test_the_title_is_drawn_big_and_centred():
    canvas = render.Canvas()
    game = Game(canvas, seed=1)
    assert isinstance(game.scene, TitleScene)
    game.scene.draw(canvas)
    width = render.font().big_width("SQL WITCH", scenes.TITLE_DOT)
    row = [x for x in range(320) if canvas.get_at((x, 39))[:3] == render.BUTTER]
    assert row and min(row) >= (320 - width) // 2 and max(row) < (320 + width) // 2 + 1


# ------------------------------------------------------------------ the sandbox

def test_the_sandbox_answers_reads_and_refuses_writes_without_crashing():
    typed = "SELECT name FROM spells LIMIT 1\nDROP TABLE spells\nDELETE * FROM spells\n" \
            "SELECT COUNT(*) FROM spells\n\n"
    run = subprocess.run([sys.executable, "-m", "try_it_yourself.try_sandbox"], cwd=ROOT,
                         input=typed, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    assert "Traceback" not in run.stderr
    assert "('Ember',)" in run.stdout
    assert "refused to listen" in run.stdout
    assert "does not understand" in run.stdout
    assert "(12,)" in run.stdout                                  # the DROP changed nothing
