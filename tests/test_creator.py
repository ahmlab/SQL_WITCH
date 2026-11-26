"""Prompt 06: layered sprites, palette swaps, the animation controller, names, the creator."""

import json
import shutil

import pytest

pygame = pytest.importorskip("pygame")

from engine import render  # noqa: E402
from engine.animation import (Animator, Character, default_look, is_default, palette_swap,  # noqa: E402
                              spec, swap_table)
from engine.audio import Silent  # noqa: E402
from engine.creator import CreatorScene  # noqa: E402
from engine.scenes import DialogueScene, Game  # noqa: E402
from i18n import CATALOG  # noqa: E402
from magic.battle import Battle  # noqa: E402
from magic.names import check_name  # noqa: E402
from save.profiles import SaveSystem  # noqa: E402
from tools import import_sprites  # noqa: E402

PALETTE = {tuple(c) for c in render.PALETTE}


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def default_player():
    yield
    CATALOG.set_player("Ada", "feminine")


def colours(surface):
    return {tuple(surface.get_at((x, y)))[:3] for x in range(surface.get_width())
            for y in range(surface.get_height()) if surface.get_at((x, y))[3]}


# ------------------------------------------------------------------ palette swap

def test_palette_swap_maps_every_swap_colour_and_nothing_else():
    s = spec()
    swaps = [tuple(c) for pair in s["swaps"].values() for c in pair]
    source = pygame.Surface((len(swaps) + 2, 1), pygame.SRCALPHA)
    for x, colour in enumerate(swaps):
        source.set_at((x, 0), colour)
    source.set_at((len(swaps), 0), render.INK)            # a palette colour: untouched
    table = swap_table({"hair_colour": "teal", "skin": "bark"})
    out = palette_swap(source, table)
    for x, colour in enumerate(swaps):
        assert tuple(out.get_at((x, 0)))[:3] == table[colour]
    assert tuple(out.get_at((len(swaps), 0)))[:3] == render.INK
    assert tuple(out.get_at((len(swaps) + 1, 0)))[3] == 0  # transparency stays transparent


@pytest.mark.parametrize("look", [default_look(), {"hair": "braid", "hair_colour": "teal",
                                                   "hat": "wide", "accessory": "glasses",
                                                   "skin": "bark", "primary": "wine"}])
def test_every_frame_and_portrait_uses_only_palette_colours(look):
    character = Character(look)
    for tag, info in spec()["tags"].items():
        for i in range(info["frames"]):
            assert colours(character.frame(tag, i)) <= PALETTE, (tag, i)
    for emotion in spec()["emotions"]:
        assert colours(character.portrait(emotion)) <= PALETTE


# ------------------------------------------------------------------ the controller

def tags():
    return spec()["tags"]


def test_idle_to_cast_and_back_with_the_projectile_event_once():
    a = Animator(tags())
    assert a.play("cast") and a.tag == "cast"
    events = []
    for _ in range(40):
        events += a.update(30)
    assert events == ["projectile"] and a.tag == "idle"


def test_hit_interrupts_a_cast_and_faint_is_terminal():
    a = Animator(tags())
    a.play("cast")
    a.update(200)
    assert a.hit() and a.tag == "hit" and a.frame == 0
    a.play("faint")
    a.update(5000)
    assert a.tag == "faint" and a.done and a.frame == tags()["faint"]["frames"] - 1
    assert not a.hit() and not a.play("idle") and a.tag == "faint"


def test_the_controller_is_deterministic_given_elapsed_time():
    one, many = Animator(tags()), Animator(tags())
    one.play("cast")
    many.play("cast")
    e1 = one.update(400)
    e2 = sum((many.update(1) for _ in range(400)), [])
    assert (one.tag, one.frame) == (many.tag, many.frame) and e1 == e2 == ["projectile"]


def test_a_guardian_can_use_the_same_controller():
    slime = {"idle": {"frames": 2, "ms": 300, "loop": True},
             "cast": {"frames": 3, "ms": 100, "events": {"2": "splat"}},
             "hit": {"frames": 2, "ms": 80}, "faint": {"frames": 3, "ms": 120, "terminal": True}}
    a = Animator(slime)
    a.play("cast")
    assert a.update(250) == ["splat"]


# ------------------------------------------------------------------ names

@pytest.mark.parametrize("name, key", [
    ("林小雨", None), ("Grace", None), ("Ember", "creator.name.taken"),
    ("SELECT", "creator.name.keyword"), ("o'malley", "creator.name.characters"),
    ("where", "creator.name.keyword"), ("Goo Spit", "creator.name.taken"),
    ("", "creator.name.empty"), ("Abcdefghijklmn", "creator.name.too_long"),
    ("a;b", "creator.name.characters"), ("back\\slash", "creator.name.characters"),
])
def test_name_rules(name, key):
    got, suggestion = check_name(name)
    assert got == key
    if key:
        assert check_name(suggestion)[0] is None          # the suggestion itself is valid
        assert CATALOG.has(key)


def test_the_name_appears_in_the_witch_row_and_in_a_cast_report():
    battle = Battle(seed=1, foe_opens=False, ada_name="林小雨")
    assert battle.conn.execute("SELECT name FROM witch").fetchone()[0] == "林小雨"
    report = battle.ada_cast("SELECT name FROM spells LIMIT 1")
    assert report.events[0][2] == "林小雨"                 # ("cast", i, caster, spell, ...)
    logged = battle.conn.execute("SELECT caster FROM query_log").fetchall()
    assert ("林小雨",) in logged


# ------------------------------------------------------------------ the creator

def type_text(game, text):
    for char in text:
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))


def key(game, k):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0))


def test_the_creator_refuses_then_accepts_and_round_trips_through_the_save(tmp_path):
    saves = SaveSystem(tmp_path)
    game = Game(render.Canvas(), seed=1, audio=Silent(), saves=saves, skip_creator=False)
    game.settings.language, game.settings.consent_asked = "en", True
    game.new_game()
    creator = game.scene
    assert isinstance(creator, CreatorScene)
    creator.name = ""
    type_text(game, "Ember")
    key(game, pygame.K_RETURN)                            # on the name row: try to finish
    assert creator.refusal[0] == "creator.name.taken" and isinstance(game.scene, CreatorScene)
    for _ in range(5):
        key(game, pygame.K_BACKSPACE)
    type_text(game, "林")                                 # a Chinese name (the IME commits it)
    creator.row = creator.rows.index("gender")
    key(game, pygame.K_RIGHT)
    creator.row = creator.rows.index("hair")
    key(game, pygame.K_RIGHT)
    creator.row = creator.rows.index("done")
    game.draw()
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, DialogueScene)
    assert CATALOG.player == {"name": "林", "gender": "masculine"}
    assert game.state.player.look["hair"] == "bob"
    saved_profile = saves.profile(game.profile_id)
    assert saved_profile["name"] == "林"
    game.save_slot("1")
    again = saves.load(game.profile_id, "1")
    assert again.player.name == "林" and again.player.look == game.state.player.look
    assert again.player.gender == "masculine"


def test_the_mirror_changes_the_look_only():
    game = Game(render.Canvas(), seed=1, audio=Silent())
    game.state.player.name = "Grace"
    back = game.scene
    mirror = CreatorScene(game, mirror=True, back=back)
    game.switch(mirror)
    assert "name" not in mirror.rows
    type_text(game, "Mallory")                             # typing changes nothing
    mirror.row = mirror.rows.index("hat")
    key(game, pygame.K_RIGHT)
    mirror.row = mirror.rows.index("done")
    key(game, pygame.K_RETURN)
    assert game.scene is back and game.state.player.name == "Grace"
    assert game.state.player.look["hat"] == "wide"


def test_a_custom_look_is_drawn_in_battle_and_follows_its_events():
    from engine.scenes import BattleScene
    game = Game(render.Canvas(), seed=1, audio=Silent())
    game.state.player.look = {"hair": "braid", "hat": "none"}
    assert not is_default(game.state.player.look) and is_default({})
    scene = BattleScene(game, "slime")
    game.switch(scene)
    for _ in range(20):
        game.update(16)
        game.draw()
    character = game.character()
    scene.ada.cast(render.RED)
    game.update(16)
    game.draw()
    assert character.animator.tag == "cast"
    from engine.dialogue import portraits
    assert portraits["ada"]("happy").get_size() == tuple(spec()["portrait_frame"])


# ------------------------------------------------------------------ the validator

def copy_art(tmp_path):
    folder = tmp_path / "witch"
    shutil.copytree(import_sprites.ASSETS / "witch", folder)
    return folder


def test_the_shipped_placeholders_pass_the_validator():
    assert import_sprites.validate() == []


def test_the_validator_rejects_a_missing_tag(tmp_path):
    folder = copy_art(tmp_path)
    meta_path = folder / "hair" / "bob.json"
    meta = json.loads(meta_path.read_text())
    meta["meta"]["frameTags"] = [t for t in meta["meta"]["frameTags"] if t["name"] != "faint"]
    meta_path.write_text(json.dumps(meta))
    assert any("no tag 'faint'" in p for p in import_sprites.validate(folder=folder))


def test_the_validator_rejects_an_off_palette_pixel(tmp_path):
    folder = copy_art(tmp_path)
    png = folder / "hat" / "wide.png"
    image = pygame.image.load(str(png))
    image.set_at((3, 3), (12, 200, 77, 255))
    pygame.image.save(image, str(png))
    assert any("not a palette or swap colour" in p for p in import_sprites.validate(folder=folder))


def test_the_validator_rejects_a_portrait_without_an_emotion(tmp_path):
    folder = copy_art(tmp_path)
    meta_path = folder / "portrait" / "accessory" / "scarf.json"
    meta = json.loads(meta_path.read_text())
    meta["meta"]["frameTags"] = meta["meta"]["frameTags"][:-1]
    meta_path.write_text(json.dumps(meta))
    assert any("surprised" in p for p in import_sprites.validate(folder=folder))
