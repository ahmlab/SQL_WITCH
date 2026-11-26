"""Prompt 05: saves, settings, display, accessibility, statistics, telemetry, the new flow."""

import json
import os
import sqlite3
from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

from engine import render  # noqa: E402
from engine import settings as settings_screen  # noqa: E402
from engine.audio import Silent  # noqa: E402
from engine.menus import ConsentScene, LanguageScene, LoadScene  # noqa: E402
from engine.scenes import BattleScene, DialogueScene, Game, ResultScene, TitleScene  # noqa: E402
from i18n import CATALOG, set_locale  # noqa: E402
from magic.db import build_db  # noqa: E402
from save import stats  # noqa: E402
from save.files import Damaged, backup_of, read_json, write_json  # noqa: E402
from save.profiles import SaveSystem  # noqa: E402
from save.settings_file import Settings, SettingsFile  # noqa: E402
from save.state import SCHEMA_VERSION, GameState  # noqa: E402
from save.telemetry import Telemetry  # noqa: E402
from story import pacing  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def clean_globals():
    yield
    set_locale("en")
    CATALOG.set_player("Ada", "feminine")
    render.set_palette("normal", settings_screen.ACCESSIBILITY["palettes"])
    render.HEAVY_TEXT[0] = False
    pacing.set_text_speed(1.0)


def key(game, k, mod=0):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))
    game.handle(pygame.event.Event(pygame.KEYUP, key=k, mod=mod))


def run(game, ms):
    for _ in range(ms // 16):
        game.update(16)
        game.draw()


def full_state() -> GameState:
    state = GameState(at="knight", beaten=["slime"], retries={"slime": 2}, runes=["LIMIT"],
                      scrolls={"fire": "SELECT name FROM spells LIMIT 1"},
                      inventory={"Ether": 1}, story={"met_grimoire": True}, region="keep",
                      position=[3, 4], companions={"bard": {"trust": 2}}, fatigue=0.3,
                      playtime_s=321.0, settings={"language": "es"},
                      telemetry={"consent": True, "share_queries": False},
                      log=[{"t": 1, "sql": "SELECT 1", "techniques": ["LIMIT"]}],
                      battles=[{"guardian": "slime", "result": "ada"}],
                      sessions=[{"start": 1, "seconds": 9}], time_in={"battle": 3.0},
                      backups={"before the keep": "snapshot-1"})
    state.player.name, state.player.gender = "Lin", "masculine"
    state.player.look = {"hair": "braid", "hat": "pointed"}
    state.codex = [{"id": "LIMIT", "by": "ada", "example": "SELECT 1 LIMIT 1",
                    "first_query": "SELECT 1 LIMIT 1", "turn_seen": 2}]
    return state


# ------------------------------------------------------------------ save files

def test_a_full_state_round_trips(tmp_path):
    saves = SaveSystem(tmp_path)
    pid = saves.create_profile("Lin")
    state = full_state()
    saves.save(pid, "2", state)
    again = saves.load(pid, "2")
    assert again.to_dict() == state.to_dict()
    assert again.to_dict()["schema_version"] == SCHEMA_VERSION


def test_a_version_1_save_migrates():
    data = json.loads((FIXTURES / "save_v1.json").read_text())
    state = GameState.from_dict(data)
    assert state.player.name == "Grace" and state.at == "knight" and state.runes == ["LIMIT"]
    assert state.scrolls["fire"].startswith("SELECT") and state.playtime_s == 754.5
    assert state.to_dict()["schema_version"] == SCHEMA_VERSION


def test_a_corrupt_slot_shows_damaged_and_offers_its_backup(tmp_path):
    saves = SaveSystem(tmp_path)
    pid = saves.create_profile()
    first, second = GameState(at="slime"), GameState(at="knight")
    saves.save(pid, "1", first)
    saves.save(pid, "1", second)                     # the first one is now the .bak
    path = saves._slot_path(pid, "1")
    path.write_text('{"schema_version": 2, "at": "kni')    # a power cut mid-write, by hand
    info = saves.slots(pid)[0]
    assert info.status == "damaged" and info.has_backup
    with pytest.raises(Damaged):
        saves.load(pid, "1")
    assert saves.load_backup(pid, "1").at == "slime"
    assert saves.latest() is None                    # Continue never picks a damaged slot


def test_an_atomic_write_survives_a_crash_at_the_rename(tmp_path, monkeypatch):
    path = tmp_path / "slot1.json"
    write_json(path, {"good": 1})
    def crash(*_):
        raise OSError("power cut")
    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError):
        write_json(path, {"good": 2})
    monkeypatch.undo()
    assert read_json(path) == ({"good": 1}, "ok")    # the old file, whole
    assert list(tmp_path.glob("*.tmp")) == []        # no half-written leftovers
    assert backup_of(path).exists()


def test_two_profiles_never_see_each_others_saves_or_statistics(tmp_path):
    saves = SaveSystem(tmp_path)
    a, b = saves.create_profile("Ana"), saves.create_profile("Bo")
    sa, sb = GameState(at="slime"), GameState(at="knight")
    sa.log = [{"sql": "SELECT * FROM enemies", "rows": 1, "read": 1, "tables": ["enemies"]}]
    saves.save(a, "1", sa)
    saves.save(b, "3", sb)
    assert [i.status for i in saves.slots(a)] == ["ok", "empty", "empty", "empty"]
    assert [i.status for i in saves.slots(b)] == ["empty", "empty", "ok", "empty"]
    assert stats.casting(saves.load(b, "3").log)["queries"] == 0
    assert stats.casting(saves.load(a, "1").log)["queries"] == 1


# ------------------------------------------------------------------ settings

class FakeScreen:
    def __init__(self):
        self.mode, self.fill, self.scale, self.shake, self.calls = "windowed", False, 3, 0, []

    def set_display(self, mode, scale, fill):
        self.calls.append((mode, scale, fill))
        self.mode, self.scale, self.fill = mode, scale, fill

    def to_logical(self, pos):
        return pos


def test_every_setting_applies_live():
    screen = FakeScreen()
    game = Game(render.Canvas(), seed=1, screen=screen, audio=Silent())
    s = game.settings
    s.language, s.display, s.fill = "es", "fullscreen", True
    s.volume.update(master=0.5, music=0.2, effects=0.7, ui=0.3)
    s.text_speed, s.auto_advance = "fast", True
    s.palette, s.grimoire_font = "deuteranopia", "large"
    settings_screen.apply(game)
    assert CATALOG.locale == "es"
    assert screen.calls[-1] == ("fullscreen", None, True)
    assert game.audio.levels == {"master": 0.5, "music": 0.2, "effects": 0.7, "ui": 0.3}
    assert pacing.SPEED["factor"] == 1.8 and game.auto_advance
    assert render.HP_COLOURS[0] == render.BLUE and render.HEAVY_TEXT[0]
    s.text_speed = "instant"
    settings_screen.apply(game)
    assert pacing.Typewriter("Hello there.", "Ada").visible(0) == len("Hello there.")
    s.display = "windowed"
    s.scale = 2
    settings_screen.apply(game)
    assert screen.calls[-1] == ("windowed", 2, True) and screen.mode == "windowed"


def test_the_settings_screen_changes_a_value_and_saves_it(tmp_path):
    saves = SaveSystem(tmp_path)
    game = Game(render.Canvas(), seed=1, audio=Silent(), saves=saves)
    scene = settings_screen.SettingsScene(game, game.scene)
    game.switch(scene)
    for row in range(len(settings_screen.ROWS)):      # every row draws, before any choice
        scene.row = row
        game.draw()
    scene.row = settings_screen.ROWS.index("text_speed")
    key(game, pygame.K_RIGHT)
    assert game.settings.text_speed == "fast" and pacing.SPEED["factor"] == 1.8
    assert SettingsFile(tmp_path).load().text_speed == "fast"
    scene.row = settings_screen.ROWS.index("bind.rewind")
    key(game, pygame.K_RETURN)                        # waits for the new key
    key(game, pygame.K_r)
    assert game.settings.bindings["rewind"] == "r"


def test_fullscreen_toggles_and_restores():
    screen = render.Screen(scale=2)
    screen.set_display("fullscreen")
    assert screen.mode == "fullscreen"
    screen.set_display("windowed", 2)
    assert screen.mode == "windowed" and screen.window.get_size() == (640, 360)


@pytest.mark.parametrize("size, k, offset", [
    ((1366, 768), 4, (43, 24)), ((1920, 1080), 6, (0, 0)),
    ((2560, 1440), 8, (0, 0)), ((3840, 2160), 12, (0, 0)),
])
def test_integer_scaling_letterboxes(size, k, offset):
    got_k, frame, got_offset = render.letterbox(size)
    assert (got_k, got_offset) == (k, offset) and frame == (320 * k, 180 * k)
    _, filled, (ox, oy) = render.letterbox(size, fill=True)
    assert filled[0] <= size[0] and filled[1] <= size[1]
    assert filled[0] >= size[0] - 2 or filled[1] >= size[1] - 2      # no bars to speak of


def test_reduced_motion_disables_shake_and_flash_in_a_battle():
    screen = FakeScreen()
    game = Game(render.Canvas(), seed=1, screen=screen, audio=Silent())
    game.settings.screen_shake = game.settings.flashes = False
    scene = BattleScene(game, "slime")
    game.switch(scene)
    run(game, 6000)                                   # the Slime opens and hits
    for char in "SELECT name FROM spells":
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))
    key(game, pygame.K_RETURN, pygame.KMOD_CTRL)
    flashes = 0
    for _ in range(300):
        game.update(16)
        flashes += scene.flash["foe"] + scene.flash["ada"]
        game.shake()
    assert flashes == 0 and screen.shake == 0


def test_a_palette_switch_changes_the_chart_colours():
    normal = dict(render.ELEMENT_COLOURS)
    render.set_palette("deuteranopia", settings_screen.ACCESSIBILITY["palettes"])
    assert render.ELEMENT_COLOURS["Fire"] != normal["Fire"]
    assert render.hp_colour(10, 100) != render.RED
    palette = set(render.PALETTE)
    assert set(render.ELEMENT_COLOURS.values()) <= palette and set(render.HP_COLOURS) <= palette


# ------------------------------------------------------------------ the flow

def win_the_battle(game):
    scene = game.scene
    scene.battle.state.foe.hp = 1
    scene.battle.conn.execute("UPDATE enemies SET hp = 1")
    for _ in range(600):
        if scene.phase == "input":
            break
        run(game, 32)
    for char in "SELECT name FROM spells LIMIT 1":
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))
    key(game, pygame.K_RETURN, pygame.KMOD_CTRL)
    for _ in range(600):
        if isinstance(game.scene, ResultScene):
            return game.scene
        run(game, 32)
    raise AssertionError("the battle never ended")


def through_dialogue(game):
    for _ in range(80):
        if not isinstance(game.scene, DialogueScene):
            return
        key(game, pygame.K_RETURN)
        key(game, pygame.K_RETURN)


def test_autosave_fires_after_a_guardian_and_not_before(tmp_path):
    saves = SaveSystem(tmp_path)
    game = Game(render.Canvas(), seed=1, audio=Silent(), saves=saves, start="slime")
    game.settings.language, game.settings.consent_asked = "en", True
    game.new_game()
    through_dialogue(game)
    assert isinstance(game.scene, BattleScene)
    auto = saves._slot_path(game.profile_id, "auto")
    assert not auto.exists()                          # not mid-battle
    result = win_the_battle(game)
    assert result.won and auto.exists()
    saved = saves.load(game.profile_id, "auto")
    assert saved.at == "knight" and "slime" in saved.beaten and "LIMIT" in saved.runes
    assert saved.log and saved.log[-1]["techniques"] == ["LIMIT"]


def test_defeat_restarts_the_battle_with_the_retry_counted():
    game = Game(render.Canvas(), seed=1, audio=Silent(), start="slime")
    scene = BattleScene(game, "slime")
    game.switch(scene)
    scene.battle.state.ada.hp = 0
    scene.battle.winner = "foe"
    result = ResultScene(game, scene.battle)
    game.switch(result)
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, BattleScene) and game.scene is not scene
    assert game.state.retries["slime"] == 1 and game.state.fatigue > 0
    ada = game.scene.battle.state.ada
    assert ada.hp == ada.max_hp and ada.mp == ada.max_mp


def test_first_launch_flow_then_tutorial_slime_and_knight(tmp_path):
    """A fresh save: language, consent, (creator skipped), the story, the tutorial, the Slime,
    the autosave, the Knight."""
    saves = SaveSystem(tmp_path)
    game = Game(render.Canvas(), seed=3, audio=Silent(), saves=saves, start="tutorial",
                skip_creator=True)
    assert game.first_launch and isinstance(game.scene, TitleScene)
    key(game, pygame.K_RETURN)                        # New Game
    assert isinstance(game.scene, LanguageScene)
    key(game, pygame.K_RETURN)                        # English
    assert isinstance(game.scene, ConsentScene)
    key(game, pygame.K_RETURN)                        # "No, thank you" is first
    assert game.settings.telemetry is False and game.settings.consent_asked
    assert isinstance(game.scene, DialogueScene) and game.profile_id
    through_dialogue(game)
    from engine.tutorial_scene import TutorialScene
    assert isinstance(game.scene, TutorialScene)
    key(game, pygame.K_ESCAPE)                        # skip the tutorial...
    key(game, pygame.K_RETURN)                        # ...yes
    for _ in range(400):
        if not isinstance(game.scene, TutorialScene):
            break
        run(game, 32)
        key(game, pygame.K_RETURN)
    through_dialogue(game)
    assert isinstance(game.scene, BattleScene) and game.scene.key == "slime"
    win_the_battle(game)
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, DialogueScene) and game.scene.guardian == "knight"
    through_dialogue(game)
    assert isinstance(game.scene, BattleScene) and game.scene.key == "knight"
    assert saves.load(game.profile_id, "auto").at == "knight"


def test_continue_loads_the_most_recent_save_and_load_offers_slots(tmp_path):
    saves = SaveSystem(tmp_path)
    pid = saves.create_profile("Ana")
    state = GameState(at="knight", runes=["LIMIT"])
    state.player.name = "Ana"
    saves.save(pid, "2", state)
    game = Game(render.Canvas(), seed=1, audio=Silent(), saves=saves)
    labels = [label for label, _ in game.scene.items()]
    assert labels[0] == "Continue"
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, DialogueScene) and game.scene.guardian == "knight"
    assert game.runes == {"LIMIT"} and CATALOG.player["name"] == "Ana"
    load = LoadScene(game, TitleScene(game))
    game.switch(load)
    assert [label for label, _ in load.items()] == ["Ana"]
    key(game, pygame.K_RETURN)
    assert any("Slot 2" in label for label, _ in load.items())


# ------------------------------------------------------------------ statistics

def fixture_state():
    data = json.loads((FIXTURES / "stats_log.json").read_text())
    state = GameState(log=data["log"], battles=data["battles"], run_id="r1")
    state.sessions = [{"start": 0, "seconds": 600}, {"start": 1, "seconds": 300}]
    state.time_in = {"battle": 270.0, "story": 120.0}
    return state


def test_statistics_match_hand_computed_values():
    state = fixture_state()
    everything = stats.summary(state, {"slime": "LIMIT", "knight": "WHERE"},
                               {"spells", "items", "enemies", "witch"})
    c = everything["casting"]
    assert (c["queries"], c["free_looks"], c["miscasts"], c["overflows"]) == (5, 1, 1, 1)
    assert (c["rows_summoned"], c["rows_read"], c["mp_spent"], c["mp_wasted"]) == (17, 9, 41, 18)
    assert c["rows_per_query"] == 3.4 and c["efficiency_trend"] == [1.0, 0.33, 1.0, 1.0, 1.0]
    tech = everything["technique"]
    assert tech["counts"] == {"LIMIT": 3, "WHERE": 1}
    assert tech["first"]["WHERE"]["guardian"] == "knight"
    assert tech["learned"]["LIMIT"] == {"guardian": "slime", "before": 0, "since": 3}
    assert tech["learned"]["WHERE"] == {"guardian": "knight", "before": 0, "since": 1}
    assert everything["tables"]["counts"] == {"spells": 3, "enemies": 1, "items": 1}
    assert everything["tables"]["never"] == ["witch"]
    assert [q["index"] for q in everything["queries"]] == [False, False, False, True, False]
    b = everything["battles"]
    assert (b["battles"], b["won"], b["rounds"], b["rewinds"], b["tricks"]) == (3, 2, 12, 3, 1)
    assert b["retries"] == {"slime": 1} and b["seconds"] == 270
    h = everything["habits"]
    assert h["sessions"] == 2 and h["seconds"] == 900 and h["fatigue"] == [0.02] * 3
    one_run = stats.summary(state, run="r1")
    assert one_run["casting"]["queries"] == 4


def test_the_export_recreates_the_scrolls_in_a_fresh_database():
    scrolls = {"fire": "SELECT name FROM spells WHERE element = 'Fire' LIMIT 1",
               "look": "SELECT * FROM enemies"}
    sql = stats.export_scrolls_sql(scrolls)
    fresh = build_db(1)
    fresh.executescript(sql)
    assert fresh.execute("SELECT COUNT(*) FROM scroll_fire").fetchone()[0] == 1
    assert fresh.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall() == \
        [("scroll_fire",), ("scroll_look",)]
    assert stats.export_csv(fixture_state().log).splitlines()[0].startswith("t,run,battle")


def test_a_real_battle_logs_real_times_and_plans():
    game = Game(render.Canvas(), seed=1, audio=Silent())
    scene = BattleScene(game, "slime")
    game.switch(scene)
    for _ in range(400):
        if scene.phase == "input":
            break
        run(game, 32)
    scene.cast("SELECT element, power FROM spells WHERE element = 'Fire'")   # a free look
    record = game.state.log[-1]
    assert record["ms"] > 0 and record["plan"] == ["SCAN spells"] and record["scanned"] > 0
    assert record["techniques"] == ["WHERE"] and record["tables"] == ["spells"]
    scene.cast("SELEC nonsense")
    assert game.state.log[-1]["miscast"]


# ------------------------------------------------------------------ telemetry

def test_telemetry_sends_nothing_without_consent(tmp_path):
    consent = {"on": False}
    telemetry = Telemetry(tmp_path, lambda: consent["on"])
    assert telemetry.record("cast", sql="SELECT 1", techniques=["LIMIT"]) is None
    sent = []
    assert telemetry.flush(lambda batch: sent.append(batch) or True) == 0
    assert sent == [] and telemetry.pending() == []


def test_with_consent_the_batch_holds_no_query_text_unless_shared(tmp_path):
    share = {"on": False}
    telemetry = Telemetry(tmp_path, lambda: True, lambda: share["on"])
    telemetry.record("cast", sql="SELECT name FROM spells", techniques=["WHERE"],
                     player="Ada", outcome="cast")
    share["on"] = True
    telemetry.record("cast", sql="SELECT 2", techniques=[])
    sent = []
    assert telemetry.flush(lambda batch: sent.extend(batch) or True) == 2
    assert "sql" not in sent[0] and "player" not in sent[0] and sent[0]["techniques"] == ["WHERE"]
    assert sent[1]["sql"] == "SELECT 2"
    assert len(sent[0]["install"]) == 32 and telemetry.pending() == []


def test_a_game_without_consent_queues_nothing(tmp_path):
    saves = SaveSystem(tmp_path)
    game = Game(render.Canvas(), seed=1, audio=Silent(), saves=saves)
    scene = BattleScene(game, "slime")
    game.switch(scene)
    run(game, 2000)
    assert game.telemetry.pending() == []
    game.settings.telemetry = True
    game.track("language", locale="es")
    assert [e["event"] for e in game.telemetry.pending()] == ["language"]


def test_changing_the_language_never_shrinks_the_window(monkeypatch):
    """The bug: each settings change re-opened the window at the "largest scale that fits",
    measured from the window itself, so it shrank one step at a time."""
    monkeypatch.setattr(render, "desktop_size", lambda: (1920, 1080))
    screen = render.Screen()
    size = screen.window.get_size()
    assert size == (1280, 720)              # HD: the largest whole multiple of 1280x720 that fits
    # As on a real desktop: once a window exists, Info() reports the window, not the monitor.
    monkeypatch.setattr(pygame.display, "Info",
                        lambda: type("Info", (), {"current_w": screen.window.get_width(),
                                                  "current_h": screen.window.get_height()})())
    game = Game(screen.canvas, seed=1, screen=screen, audio=Silent())
    for language in ("es", "zh-Hans", "zh-Hant", "en", "es"):
        game.settings.language = language
        settings_screen.apply(game)
        assert screen.window.get_size() == size
    game.settings.volume["music"] = 0.3                 # any other setting: the same
    settings_screen.apply(game)
    assert screen.window.get_size() == size
    game.settings.scale = 2                             # a real change still applies
    settings_screen.apply(game)
    assert screen.window.get_size() == (640, 360)


# ------------------------------------------------------------------ after the end (bug report)

def finished_profile(tmp_path):
    saves = SaveSystem(tmp_path)
    SettingsFile(saves.root).save(Settings(language="en", consent_asked=True))
    pid = saves.create_profile("Ada")
    state = GameState(at="end", beaten=["slime", "knight"], runes=["LIMIT", "WHERE"])
    saves.save(pid, "auto", state)
    game = Game(render.Canvas(), seed=1, audio=Silent(), saves=saves,
                settings=SettingsFile(saves.root).load(), start="tutorial", skip_creator=False)
    return saves, pid, game


def test_continue_after_the_end_plays_again_keeping_what_was_learned(tmp_path):
    saves, pid, game = finished_profile(tmp_path)
    key(game, pygame.K_RETURN)                         # Continue
    assert isinstance(game.scene, DialogueScene) and game.scene.guardian == "slime"
    assert game.runes == {"LIMIT", "WHERE"} and game.profile_id == pid


def test_new_game_after_continuing_a_finished_run_starts_the_story(tmp_path):
    from engine.creator import CreatorScene
    saves, pid, game = finished_profile(tmp_path)
    key(game, pygame.K_RETURN)                         # Continue: a finished run
    game.switch(TitleScene(game))
    game.new_game()
    assert isinstance(game.scene, CreatorScene)
    game.scene.finish()                                # Done (the name Ada is valid)
    assert isinstance(game.scene, DialogueScene) and game.scene.guardian == "tutorial"
    assert game.profile_id != pid and game.runes == set()


def test_a_profile_with_no_save_can_be_played_and_profiles_can_be_deleted(tmp_path):
    saves, pid, game = finished_profile(tmp_path)
    empty = saves.create_profile("Lin", {"hair": "bob"})
    load = LoadScene(game, game.scene)
    game.switch(load)
    labels = [label for label, _ in load.items()]
    assert any("Lin" in label and "no saves yet" in label for label in labels)
    load.choice = next(i for i, label in enumerate(labels) if "Lin" in label)
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DELETE, mod=0))
    assert load.confirm["id"] == empty
    key(game, pygame.K_ESCAPE)                         # keep it
    assert any(p["id"] == empty for p in saves.profiles())
    key(game, pygame.K_RETURN)                         # ENTER on Lin: play its story
    assert isinstance(game.scene, DialogueScene) and CATALOG.player["name"] == "Lin"
    assert game.profile_id == empty and game.state.player.look == {"hair": "bob"}
    load = LoadScene(game, TitleScene(game))
    game.switch(load)
    labels = [label for label, _ in load.items()]
    load.choice = next(i for i, label in enumerate(labels) if label.startswith("Ada"))
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DELETE, mod=0))
    game.draw()                                        # the question is on screen
    key(game, pygame.K_RETURN)                         # delete Ada for good
    assert [p["name"] for p in saves.profiles()] == ["Lin"]
    assert not (tmp_path / "profiles" / pid).exists()
