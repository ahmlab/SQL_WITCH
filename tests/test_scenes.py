import pytest

pygame = pytest.importorskip("pygame")

from engine import render
from engine.grimoire import (RIGHT_PAGE, ROW_H, TABLE_TOP, TEXT_DY, Grimoire, foe_summary,
                             wrap)
from engine.scenes import (BattleScene, DialogueScene, Game, ResultScene, TitleScene)
from engine.textinput import QueryEditor
from magic.battle import Battle
from magic.cast import PAGE_ROWS


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


def key(game, k, mod=0):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))


def type_text(game, text):
    for char in text:
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))


def cast(game, sql):
    type_text(game, sql)
    key(game, pygame.K_RETURN, pygame.KMOD_LCTRL)


def run(game, ms):
    for _ in range(ms // 16):
        game.update(16)
        game.draw()


def until_input(game, limit_ms=60_000):
    """Let animations play until Ada may type again (or the battle is over)."""
    for _ in range(limit_ms // 100):
        if not isinstance(game.scene, BattleScene) or game.scene.phase == "input":
            return
        run(game, 100)


def to_battle(seed=7):
    game = Game(pygame.Surface((320, 180)), seed=seed)
    key(game, pygame.K_RETURN)                  # title -> dialogue
    key(game, pygame.K_ESCAPE)                  # skip the intro
    return game


# ------------------------------------------------------------------ the page

def test_row_five_is_cut_in_half_by_the_page():
    clip_height = RIGHT_PAGE.height - TABLE_TOP
    fifth_top = TABLE_TOP + PAGE_ROWS * ROW_H + TEXT_DY
    assert fifth_top < clip_height < fifth_top + 5            # some of its letters, not all
    fourth_bottom = TABLE_TOP + (PAGE_ROWS - 1) * ROW_H + TEXT_DY + 5
    assert fourth_bottom <= clip_height                        # row four is fully readable


def test_the_table_may_be_wider_than_the_page_and_the_clip_cuts_it():
    battle = Battle(seed=1)
    report = battle.ada_cast("SELECT * FROM spells")
    grimoire = Grimoire(QueryEditor())
    grimoire.show_result(report, now=0, looks_left=3)
    canvas = render.Canvas()
    grimoire.draw(canvas, now=5000, focused=False)
    # "unlock_level" starts past the right edge: it is drawn, but only inside the page's clip.
    header = [op for op in canvas.ops if op[0] == "text" and op[1] == "unlock_level"]
    assert header and header[0][2] > RIGHT_PAGE.right
    assert header[0][5].right == RIGHT_PAGE.right


def grimoire_pixels_below_page(sql):
    battle = Battle(seed=1, ada_runes={"LIMIT"})
    report = battle.ada_cast(sql)
    grimoire = Grimoire(QueryEditor())
    grimoire.show_result(report, now=0, looks_left=3)
    surface = pygame.Surface((320, 180))
    grimoire.draw(surface, now=5000, focused=False)
    band = [surface.get_at((x, y))[:3] for x in range(RIGHT_PAGE.x, RIGHT_PAGE.right)
            for y in range(RIGHT_PAGE.bottom + 4, RIGHT_PAGE.bottom + 9)]
    return band.count(render.GREY)


def test_ink_drips_only_when_rows_overflow():
    assert grimoire_pixels_below_page("SELECT * FROM spells") > 0
    assert grimoire_pixels_below_page("SELECT name FROM spells LIMIT 1") == 0


def test_wrap_and_foe_summary():
    assert wrap("SELECT * FROM foe_spells WHERE foe_id = 1 LIMIT 2", 36) == \
        ["SELECT * FROM foe_spells WHERE", "foe_id = 1 LIMIT 2"]
    battle = Battle(seed=1)
    battle.ada_cast("SELECT name FROM spells")
    turn = battle.foe_act()
    assert foe_summary(turn.report).startswith(f"{len(turn.report.rows)} rows")


# ------------------------------------------------------------------ the scenes

def test_title_dialogue_battle_flow():
    game = Game(pygame.Surface((320, 180)), seed=1)
    assert isinstance(game.scene, TitleScene)
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, DialogueScene)
    key(game, pygame.K_RETURN)                  # finishes the first line at once
    assert game.scene.index == 0
    key(game, pygame.K_RETURN)                  # then moves on
    assert game.scene.index == 1
    for _ in range(60):
        if isinstance(game.scene, BattleScene):
            break
        key(game, pygame.K_RETURN)
    assert isinstance(game.scene, BattleScene)


def test_escape_on_the_title_quits_and_window_close_quits():
    game = Game(pygame.Surface((320, 180)), seed=1)
    key(game, pygame.K_ESCAPE)
    assert not game.running
    game = Game(pygame.Surface((320, 180)), seed=1)
    game.handle(pygame.event.Event(pygame.QUIT))
    assert not game.running


def test_a_miscast_shows_on_the_page_and_keeps_the_turn():
    game = to_battle()
    cast(game, "DROP TABLE spells")
    scene = game.scene
    assert "MY LIFE" in scene.grimoire.miscast
    assert scene.phase == "input" and scene.battle.state.ada.mp == 30


def test_a_scry_keeps_the_turn():
    game = to_battle()
    cast(game, "SELECT * FROM enemies")
    assert game.scene.phase == "input"
    assert game.scene.battle.state.scries_used == 1


def test_f1_toggles_the_debug_overlay():
    game = to_battle()
    key(game, pygame.K_F1)
    assert game.debug
    run(game, 100)                              # draws the overlay without crashing
    key(game, pygame.K_F1)
    assert not game.debug


def test_a_whole_battle_reaches_the_result_screen_and_can_restart():
    game = to_battle(seed=7)
    for _ in range(40):
        until_input(game)
        if not isinstance(game.scene, BattleScene):
            break
        runes = game.scene.battle.state.ada.runes
        cast(game, "SELECT name FROM spells LIMIT 1" if "LIMIT" in runes
             else "SELECT name FROM spells")
    run(game, 3000)
    assert isinstance(game.scene, ResultScene)
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, BattleScene) and game.seed == 8


def test_the_invitation_unlocks_the_rune_in_the_editor():
    game = to_battle(seed=7)
    for _ in range(40):
        until_input(game)
        if not isinstance(game.scene, BattleScene):
            break
        if "LIMIT" in game.scene.battle.state.ada.runes:
            assert "LIMIT" in game.scene.editor.unlocked
            return
        for _ in range(4):                      # stay passive so the Slime lives on
            cast(game, "SELECT * FROM enemies")
    pytest.fail("the Slime never showed LIMIT")


def test_visual_effects_do_not_change_the_battle():
    """Screen shake and animations use their own rng: the game plays exactly like Battle."""
    game = to_battle(seed=11)
    plain = Battle(seed=11)
    for _ in range(3):
        until_input(game)
        if not isinstance(game.scene, BattleScene):
            break
        cast(game, "SELECT name FROM spells")
        plain.ada_cast("SELECT name FROM spells")
        if plain.whose_turn == "foe":
            plain.foe_act()
    until_input(game)
    log = "SELECT turn, caster, sql, rows_cast FROM query_log"
    assert game.scene.battle.conn.execute(log).fetchall() == plain.conn.execute(log).fetchall()
