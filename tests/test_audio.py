import json
import wave

import pytest

pygame = pytest.importorskip("pygame")

from engine.audio import AUDIO_DIR, CONFIG, Audio, Silent
from engine.scenes import BattleScene, Game, ResultScene


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


def config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def test_every_configured_sound_is_a_real_wav_file():
    entries = list(config()["effects"].values()) + list(config()["music"].values())
    for entry in entries:
        assert 0 < entry["volume"] <= 1
        for name in entry.get("files", [entry.get("file")]):
            with wave.open(str(AUDIO_DIR / name)) as w:
                assert w.getnframes() > 0


def test_the_battle_music_loops_without_a_click():
    with wave.open(str(AUDIO_DIR / config()["music"]["battle"]["file"])) as w:
        frames = w.readframes(w.getnframes())
    first = int.from_bytes(frames[:2], "little", signed=True)
    last = int.from_bytes(frames[-2:], "little", signed=True)
    assert abs(first) < 200 and abs(last) < 200


def play_a_battle(seed=7):
    audio = Silent()
    game = Game(pygame.Surface((320, 180)), seed=seed, audio=audio)
    key = lambda k, mod=0: game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))
    key(pygame.K_RETURN)                                # title -> story
    for _ in range(60):                                 # read the whole story
        if isinstance(game.scene, BattleScene):
            break
        key(pygame.K_RETURN)
        for _ in range(4):
            game.update(16)
    for _ in range(400):
        if isinstance(game.scene, ResultScene):
            break
        if isinstance(game.scene, BattleScene) and game.scene.phase == "input":
            for char in "SELECT name FROM spells":
                game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))
            key(pygame.K_RETURN, pygame.KMOD_LCTRL)
        for _ in range(6):
            game.update(16)
    return game, audio


def test_a_battle_asks_for_the_right_sounds_and_all_of_them_exist():
    game, audio = play_a_battle()
    played = set(audio.counts)
    assert {"confirm", "cast", "hit", "hp_down", "mp_down", "mp_up", "fizzle",
            "flatline", "book", "typing", "rune"} <= played
    assert ("victory" in played) or ("defeat" in played)
    assert played <= set(config()["effects"])           # nothing the config lacks


def test_missing_files_and_a_missing_config_are_silent_not_fatal(tmp_path):
    (tmp_path / "sounds.json").write_text(json.dumps(
        {"effects": {"hit": {"file": "nope.wav"}}, "music": {"battle": {"file": "nope.wav"}}}))
    audio = Audio(tmp_path / "sounds.json")
    audio.play("hit")
    audio.play("not_configured")
    audio.play_music("battle")
    Audio(tmp_path / "missing.json").play("hit")


def test_the_real_mixer_plays_effects_and_music():
    audio = Audio()                                      # SDL dummy audio driver in tests
    audio.play("hit")
    audio.play_music("battle")
    audio.stop_music(0)


def test_f2_mutes_and_unmutes():
    game = Game(pygame.Surface((320, 180)), seed=1, audio=Silent())
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F2, mod=0))
    assert game.audio.muted
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F2, mod=0))
    assert not game.audio.muted
