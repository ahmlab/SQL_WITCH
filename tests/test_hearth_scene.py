"""The Hearth on screen (prompt 08 §2): its menu, the desks, letters, leaving."""

import pygame
import pytest

from engine import render
from engine.audio import Silent
from engine.hearth import HearthScene, NameScene, QueryDesk, ShelfScene
from engine.scenes import BattleScene, DialogueScene, Game


def key(game, k, mod=0):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))


def type_text(game, text):
    for ch in text:
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=ch))


def through(game):
    for _ in range(60):
        if not isinstance(game.scene, DialogueScene):
            return
        key(game, pygame.K_RETURN)
        key(game, pygame.K_RETURN)


@pytest.fixture
def game():
    pygame.init()
    g = Game(render.Canvas(), seed=2, audio=Silent())
    g.state.beaten = ["slime"]
    g.fatigue.value = 0.7
    g.switch(HearthScene(g, "knight"))
    through(g)
    assert isinstance(g.scene, HearthScene)
    return g


def choose(game, label_part):
    labels = [label for label, _ in game.scene.items()]
    game.scene.choice = next(i for i, l in enumerate(labels) if label_part in l)
    key(game, pygame.K_RETURN)


def test_the_hearth_greets_then_shows_its_menu_and_draws(game):
    labels = [label for label, _ in game.scene.items()]
    assert labels[0] == "Sleep" and "Talk to Marta" in labels and labels[-1] == "Leave"
    game.draw()


def test_sleep_from_the_menu_resets_fatigue_and_says_so(game):
    choose(game, "Sleep")
    assert game.fatigue.value == 0.0 and game.state.fatigue == 0.0
    assert game.scene.message


def test_cooking_is_a_query_at_the_pot(game):
    choose(game, "Cook")
    assert isinstance(game.scene, QueryDesk)
    game.scene.editor.set_text("")
    type_text(game, "SELECT name FROM recipes WHERE needs = 'Barley'")
    key(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
    assert game.scene.finished and game.fatigue.value == pytest.approx(0.45)
    game.draw()
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, HearthScene) and game.scene.message


def test_a_refused_query_at_the_pot_changes_nothing(game):
    choose(game, "Cook")
    game.scene.editor.set_text("DELETE FROM pantry")
    key(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
    assert game.scene.error and game.fatigue.value == 0.7
    game.draw()


def test_a_letter_is_read_as_a_scene_and_then_it_is_kept(game):
    choose(game, "Letter box")
    assert isinstance(game.scene, DialogueScene)
    through(game)
    assert isinstance(game.scene, HearthScene)
    assert game.state.story["letters_read"] == ["letter_1"]
    assert game.fatigue.focused


def test_buying_at_the_stall_changes_the_satchel_and_purse(game):
    game.state.coins, game.state.inventory = 30, {"Ether": 1}
    choose(game, "stall")
    assert isinstance(game.scene, QueryDesk)
    key(game, pygame.K_RETURN, pygame.KMOD_LCTRL)            # the shopkeeper's draft
    assert game.state.inventory["Healing Herb"] == 1 and game.state.coins == 24
    game.draw()


def test_a_world_backup_is_named_and_kept(game):
    choose(game, "World backup")
    assert isinstance(game.scene, NameScene)
    type_text(game, "before the clock")
    key(game, pygame.K_RETURN)
    assert "before the clock" in game.state.backups and isinstance(game.scene, HearthScene)


def test_the_shelf_lists_and_throws_away_scrolls(game):
    game.scrolls = {"ember": "SELECT name FROM spells LIMIT 1"}
    choose(game, "Scroll shelf")
    assert isinstance(game.scene, ShelfScene)
    game.draw()
    key(game, pygame.K_DELETE)
    assert game.scrolls == {}


def test_leaving_without_sleep_marta_notices_then_the_road(game):
    choose(game, "Leave")
    assert game.state.story["skipped_sleeps"] == 1
    for _ in range(30):
        if isinstance(game.scene, BattleScene):
            break
        if isinstance(game.scene, DialogueScene):
            through(game)
        else:
            for _ in range(20):
                game.update(100)
            key(game, pygame.K_RETURN)
    assert isinstance(game.scene, BattleScene) and game.scene.key == "knight"


def test_a_spent_witch_wakes_at_the_hearth_rested():
    pygame.init()
    g = Game(render.Canvas(), seed=2, audio=Silent())
    g.state.beaten = ["slime"]
    g.fatigue.value = 0.99
    g.switch(HearthScene(g, "knight", woke=True))
    assert g.fatigue.value == 0.0
    assert isinstance(g.scene, DialogueScene) and g.scene.key == "hearth_woke"


@pytest.mark.parametrize("winner", ["ada", "foe"])
def test_a_faint_at_the_end_of_a_battle_wakes_at_the_hearth(winner):
    from engine.scenes import ResultScene
    from magic.battle import Battle
    pygame.init()
    g = Game(render.Canvas(), seed=2, audio=Silent())
    g.fatigue.value = 0.99
    battle = Battle(seed=1, guardian="slime", fatigue=g.fatigue)
    battle.winner, battle.fainted = winner, True
    g.switch(ResultScene(g, battle))
    g.draw()
    key(g, pygame.K_RETURN)
    assert isinstance(g.scene, DialogueScene) and g.scene.key == "hearth_woke"
    through(g)
    assert isinstance(g.scene, HearthScene)
    assert g.scene.after == ("knight" if winner == "ada" else "slime")
    assert g.fatigue.value == 0.0


def test_after_a_victory_the_hearth_comes_before_the_next_guardian():
    from engine.scenes import ResultScene
    from magic.battle import Battle
    pygame.init()
    g = Game(render.Canvas(), seed=2, audio=Silent())
    battle = Battle(seed=1, guardian="slime")
    battle.winner = "ada"
    g.switch(ResultScene(g, battle))
    assert g.state.inventory and g.state.coins
    key(g, pygame.K_RETURN)
    through(g)
    assert isinstance(g.scene, HearthScene) and g.scene.after == "knight"
