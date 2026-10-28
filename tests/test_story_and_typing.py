import pytest

pygame = pytest.importorskip("pygame")

from engine import fx, render, scenery
from engine.audio import Silent
from engine.scenes import BattleScene, DialogueScene, Game, load_dialogue


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


class Recorder(Silent):
    """Remembers every (sound, variant) the game asked for."""

    def __init__(self):
        super().__init__()
        self.log = []

    def play(self, name, variant=0):
        self.log.append((name, variant))
        super().play(name, variant)


def key(game, k, mod=0):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))


def type_text(game, text):
    for char in text:
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))


def run(game, ms):
    for _ in range(ms // 16):
        game.update(16)
        game.draw()


# ------------------------------------------------------------------ the story

def test_the_story_goes_office_void_glade_and_ada_falls_asleep_step_by_step():
    lines = load_dialogue()["intro"]
    scenes = [line["scene"] for line in lines]
    assert scenes[0] == "office" and "void" in scenes and scenes[-1] == "glade"
    assert scenes.index("void") < scenes.index("glade")
    sleep = [line["sleep"] for line in lines if line["scene"] == "office"]
    assert sleep == sorted(sleep) and sleep[0] == 0 and sleep[-1] == 3
    first_grimoire = next(i for i, line in enumerate(lines) if line["speaker"] == "Grimoire")
    assert lines[first_grimoire].get("book") and lines[first_grimoire].get("sound") == "book"


def to_story():
    game = Game(pygame.Surface((320, 180)), seed=1, audio=Recorder())
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, DialogueScene)
    return game


def advance(game):
    key(game, pygame.K_RETURN)                  # finish the line
    key(game, pygame.K_RETURN)                  # next line


def test_ada_drifts_off_slowly_not_at_once():
    game = to_story()
    advance(game)                               # sleep 0 -> 1
    run(game, 200)
    assert 0 < game.scene.drowsy < 1
    run(game, 3000)
    assert game.scene.drowsy == 1


def test_a_new_place_dips_to_black_and_the_book_appears_with_its_sound():
    game = to_story()
    scene = game.scene
    while scene.line["scene"] == "office":
        advance(game)
    assert scene.backdrop == "void" and scene.fade_from == "office"
    assert ("flatline", 0) in game.audio.log
    while not scene.line.get("book"):
        advance(game)
    assert scene.book_born is not None and ("book", 0) in game.audio.log
    run(game, 1500)                             # the book draws, floating and speaking


@pytest.mark.parametrize("drowsy", [0, 0.5, 1.5, 2.5, 3])
def test_every_stage_of_the_office_draws(drowsy):
    canvas = render.Canvas()
    scenery.draw_office(canvas, 1234, drowsy, 0.97)
    scenery.draw_void(canvas, 500)
    for age in (-10, 100, 2000):
        scenery.draw_book(canvas, (198, 72), 777, age, speaking=age > 1000)


# ------------------------------------------------------------------ typing

def to_battle():
    game = Game(pygame.Surface((320, 180)), seed=7, audio=Recorder())
    key(game, pygame.K_RETURN)
    key(game, pygame.K_ESCAPE)
    assert isinstance(game.scene, BattleScene)
    game.audio.log.clear()
    return game


def test_the_letters_of_a_word_climb_the_scale():
    game = to_battle()
    type_text(game, "SEL")
    assert game.audio.log == [("typing", 0), ("typing", 1), ("typing", 2)]


def test_finishing_a_keyword_makes_it_glow_and_chime():
    game = to_battle()
    type_text(game, "SELECT ")
    assert ("rune", 0) in game.audio.log
    assert game.scene.word_glow is not None
    assert game.scene.fx.busy()                 # sparks and bolts are flying


def test_a_locked_keyword_thuds_instead():
    game = to_battle()
    type_text(game, "LIMIT ")
    assert ("locked", 0) in game.audio.log and ("rune", 0) not in game.audio.log


def test_erase_and_newline_have_their_own_sounds():
    game = to_battle()
    type_text(game, "SELECT name")
    key(game, pygame.K_BACKSPACE)
    key(game, pygame.K_RETURN)
    assert ("erase", 0) in game.audio.log and ("newline", 0) in game.audio.log


def test_arrow_keys_that_type_nothing_stay_silent():
    game = to_battle()
    key(game, pygame.K_LEFT)
    key(game, pygame.K_F3)
    assert game.audio.log == []


def test_typing_fast_heats_the_page():
    game = to_battle()
    type_text(game, "SELECT name FROM")
    assert game.scene.streak.level(game.scene.time) == 1.0
    run(game, 1500)
    assert game.scene.streak.level(game.scene.time) == 0.0


def test_a_hit_fires_a_bolt_from_caster_to_target():
    game = to_battle()
    type_text(game, "SELECT name FROM spells")
    key(game, pygame.K_RETURN, pygame.KMOD_LCTRL)
    bolts = 0
    for _ in range(60):
        run(game, 50)
        bolts += sum(1 for b in game.scene.fx.bolts if b.segments == 8)
    assert bolts > 0


def test_effects_expire():
    effects = fx.Effects(__import__("random").Random(1))
    effects.burst(10, 10)
    effects.zap(10, 10)
    effects.bolt((0, 0), (50, 50))
    canvas = pygame.Surface((320, 180))
    for _ in range(40):
        effects.update(16)
        effects.draw(canvas)
    assert not effects.busy()
