"""The danger theme switch and the choice of battle theme (engine/audio.py, engine/scenes.py)."""

import random

import pytest

pygame = pytest.importorskip("pygame")

from engine import render
from engine.audio import DANGER, THEME, Audio, Silent, pick_track
from engine.scenes import DANGER_OFF_ABOVE, BattleScene, Beat, Game, ResultScene
from engine.tutorial_scene import TutorialScene


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


def battle(guardian="slime", seed=3, game=None):
    game = game or Game(pygame.Surface((320, 180)), seed=seed, audio=Silent())
    scene = BattleScene(game, guardian)
    game.switch(scene)
    return game, scene


def set_hp(scene, ratio, frames=3):
    """Put Ada's HP (and the bar showing it) at a ratio, then let a few frames pass."""
    ada = scene.battle.state.ada
    ada.hp = round(ada.max_hp * ratio)
    scene.shown["ada"][0] = ada.hp
    scene.bars["ada"][0] = float(ada.hp)
    for _ in range(frames):
        scene.update(16)


def dangers(audio):
    return [entry for entry in audio.music_log if entry.startswith("danger")]


# ------------------------------------------------------------------ the danger switch

def test_dropping_below_a_quarter_turns_the_danger_theme_on_once():
    game, scene = battle()
    set_hp(scene, 0.5)
    assert not game.audio.danger
    set_hp(scene, render.HP_DANGER - 0.05)
    assert game.audio.danger and dangers(game.audio) == ["danger on"]
    set_hp(scene, 0.1, frames=30)                            # staying low: no retrigger
    assert dangers(game.audio) == ["danger on"]


def test_a_gap_between_the_thresholds_keeps_it_from_flapping():
    game, scene = battle()
    set_hp(scene, 0.2)
    set_hp(scene, (render.HP_DANGER + DANGER_OFF_ABOVE) / 2)  # healed a little: still on
    assert game.audio.danger
    set_hp(scene, DANGER_OFF_ABOVE + 0.05)                   # healed enough: off
    assert not game.audio.danger
    assert dangers(game.audio) == ["danger on", "danger off"]


def test_the_switch_follows_the_bar_not_the_hidden_hp():
    game, scene = battle()
    scene.battle.state.ada.hp = 1                            # the hit is not shown yet
    scene.bars["ada"][0] = float(scene.battle.state.ada.max_hp)
    scene.shown["ada"][0] = scene.battle.state.ada.max_hp
    scene.beats.append(Beat("...", 10 ** 6))                 # the narration is still talking
    scene.update(16)
    assert not game.audio.danger


def test_leaving_the_battle_stops_everything():
    game, scene = battle()
    set_hp(scene, 0.1)
    game.switch(ResultScene(game, scene.battle))
    assert game.audio.music is None and not game.audio.danger
    assert game.audio.music_log[-1] == "stop"


def test_the_tutorial_never_plays_the_danger_theme():
    game = Game(pygame.Surface((320, 180)), seed=2, audio=Silent())
    scene = TutorialScene(game)
    game.switch(scene)
    set_hp(scene, 0.05, frames=10)
    assert not game.audio.danger and dangers(game.audio) == []


def test_mute_still_works_and_silent_still_records():
    game, scene = battle()
    game.audio.toggle_mute()
    set_hp(scene, 0.1)
    assert game.audio.muted and game.audio.danger


# ------------------------------------------------------------------ the real mixer

def test_the_real_mixer_cross_fades_and_resumes_the_battle_theme():
    audio = Audio()                                          # SDL's dummy audio driver
    if not audio.enabled:
        pytest.skip("no mixer")
    assert audio.play_music("slime", 1) == audio.music_files("slime")[1]
    audio.update(700)
    assert audio._fades[THEME][0] == 1.0
    audio.set_danger(True)
    audio.update(700)
    assert audio._fades[THEME][0] == 0.0 and audio._fades[DANGER][0] == 1.0
    audio.set_danger(True)                                   # asked again: nothing restarts
    assert audio.music_log.count("danger on") == 1
    audio.set_danger(False)
    audio.update(700)
    assert audio._fades[THEME][0] == 1.0 and audio._fades[DANGER][0] == 0.0
    audio.toggle_mute()
    assert pygame.mixer.Channel(THEME).get_volume() == 0.0
    audio.toggle_mute()
    audio.stop_music(0)


# ------------------------------------------------------------------ choosing a theme

def test_pick_track_never_repeats_the_last_one():
    files = ["a.wav", "b.wav", "c.wav"]
    rng = random.Random(1)
    last = None
    for _ in range(50):
        last_index = pick_track(files, last, rng)
        assert files[last_index] != last
        last = files[last_index]
    assert pick_track(["only.wav"], "only.wav", rng) == 0


def test_each_battle_picks_from_its_list_and_a_retry_sounds_different():
    game, scene = battle()
    files = game.audio.music_files("slime")
    played = [game.audio.music_file]
    for _ in range(8):                                       # retry after retry
        battle(game=game)
        played.append(game.audio.music_file)
    assert set(played) <= set(files) and len(set(played)) > 1
    assert all(a != b for a, b in zip(played, played[1:]))


def test_the_tutorial_plays_the_calm_theme_and_the_slime_then_plays_another():
    game = Game(pygame.Surface((320, 180)), seed=2, audio=Silent())
    game.switch(TutorialScene(game))
    assert game.audio.music == "dummy" and game.audio.music_file == "theme_lantern.wav"
    game.switch(BattleScene(game, "slime"))
    assert game.audio.music_file != "theme_lantern.wav"


def test_the_same_seed_gives_the_same_battle_whichever_track_was_picked():
    results = []
    for warm_up in (0, 1, 2, 5):
        game = Game(pygame.Surface((320, 180)), seed=11, audio=Silent())
        for _ in range(warm_up):
            game.vfx.random()                                # a different track gets picked
        game.switch(BattleScene(game, "slime"))
        b = game.scene.battle
        turn = b.foe_act()
        report = b.ada_cast("SELECT name FROM spells")
        results.append((game.audio.music_file, turn.sql,
                         tuple((c.spell, c.damage) for c in report.casts), b.rng.random()))
    assert len({r[0] for r in results}) > 1                  # different music...
    assert len({r[1:] for r in results}) == 1                # ...the very same fight
