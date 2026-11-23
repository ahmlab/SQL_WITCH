"""Prompt 03: the script format, pacing, wrapping, the dialogue scene and the Hint Director."""

import pytest

pygame = pytest.importorskip("pygame")

from engine import render  # noqa: E402
from engine.audio import Silent  # noqa: E402
from engine.dialogue import DialogueBox, measure, wrap_text  # noqa: E402
from engine.scenes import BattleScene, DialogueScene, Game  # noqa: E402
from magic.battle import Battle  # noqa: E402
from story import hints as hints_module  # noqa: E402
from story.hints import HintDirector, context_of, mode_of  # noqa: E402
from story.pacing import Typewriter, voice  # noqa: E402
from story.scenes import legacy, scene_lines  # noqa: E402
from story.script import (Choice, ScriptError, ScriptRunner, all_scripts, dump, evaluate,  # noqa: E402
                          parse, plain, tokens)

SAMPLE = """\
# a sample with every feature
== glade ==
[scene glade] [book] [sfx book]
Grimoire: Welcome, witch. {pause 300} Here the world is a {color gold}database{/color}.
Ada: A... {speed slow}talking{speed normal} book? {wave}Wow{/wave} {shake}help{/shake}
[portrait ada sad] Ada: Is {rune WHERE} a spell?
<<if codex.WHERE>>
Grimoire: You already know WHERE.
<<elif integrity == damaged>>
Grimoire: You broke something.
<<else>>
Grimoire: You will learn it.
<<endif>>
<<set met_grimoire = true>>
-> Who are you? => who
-> Let's go. => go

== who ==
[music hearth]
Grimoire: Your Grimoire.
<<jump go>>

== go ==
: They walk on.
[end]
"""


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


class Recorder(Silent):
    def __init__(self):
        super().__init__()
        self.log = []

    def play(self, name, variant=0):
        self.log.append((name, variant))
        super().play(name, variant)


def key(game, k, mod=0, up=True):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))
    if up:
        game.handle(pygame.event.Event(pygame.KEYUP, key=k, mod=mod))


def run(game, ms):
    for _ in range(ms // 16):
        game.update(16)
        game.draw()


def shape(script):
    return [(n.id, [(type(i).__name__, getattr(i, "speaker", None), getattr(i, "text", None),
                     getattr(i, "directions", None), getattr(i, "kind", None),
                     getattr(i, "arg", None), getattr(i, "options", None)) for i in n.items])
            for n in script.nodes.values()]


# ------------------------------------------------------------------ the script format

def test_the_parser_round_trips_a_sample_script():
    script = parse(SAMPLE, "sample")
    again = parse(dump(script), "sample")
    assert shape(again) == shape(script)
    assert again.keys() == script.keys()
    first = script.node("glade").items[0]
    assert first.speaker == "Grimoire" and first.key == "story.sample.glade.1"
    assert first.directions == [("scene", ["glade"]), ("book", []), ("sfx", ["book"])]
    assert script.node("glade").items[2].directions == [("portrait", ["ada", "sad"])]


@pytest.mark.parametrize("name, script", sorted(all_scripts().items()))
def test_every_script_in_the_game_round_trips(name, script):
    assert shape(parse(dump(script), name)) == shape(script)


@pytest.mark.parametrize("text, line, words", [
    ("Grimoire: hello", 1, "before the first node"),
    ("== a ==\nGrimoire: hi\n== a ==", 3, "defined twice"),
    ("== a ==\n<<if x>>\nGrimoire: hi", 3, "never closed"),
    ("== a ==\n<<endif>>", 2, "without an <<if>>"),
    ("== a ==\n<<frobnicate>>", 2, "unknown command"),
    ("== a ==\n-> go somewhere", 2, "-> text => node_name"),
    ("== a ==\n-> go => nowhere", 2, "no node 'nowhere'"),
    ("== a ==\nGrimoire: {wave oops", 2, "unbalanced"),
    ("== a ==\njust some words", 2, "not a line"),
])
def test_malformed_scripts_say_file_line_and_what_is_wrong(text, line, words):
    with pytest.raises(ScriptError) as error:
        parse(text, "broken.script")
    assert error.value.file == "broken.script" and error.value.line == line
    assert words in str(error.value) and f"line {line}" in str(error.value)


def test_the_runner_follows_conditions_variables_choices_and_jumps():
    script = parse(SAMPLE, "sample")
    runner = ScriptRunner(script, "glade", {"codex": {"WHERE": True}})
    said = []
    while (item := runner.next()) is not None:
        if isinstance(item, Choice):
            assert [o[0] for o in item.options] == ["Who are you?", "Let's go."]
            runner.choose(item, 0)
            continue
        said.append(plain(item.text))
    assert said[3] == "You already know WHERE."
    assert said[-2:] == ["Your Grimoire.", "They walk on."]
    assert runner.variables["met_grimoire"] is True
    damaged = ScriptRunner(script, "glade", {"integrity": "damaged"}).lines()
    assert plain(damaged[3].text) == "You broke something."
    assert plain(ScriptRunner(script, "glade", {}).lines()[3].text) == "You will learn it."


@pytest.mark.parametrize("expression, expected", [
    ("codex.WHERE", True), ("not codex.WHERE", False), ("codex.LIMIT", False),
    ("integrity == damaged", True), ("fatigue > 0.7", True), ("fatigue > 0.9", False),
    ("not fatigue > 0.9 and integrity != intact", True), ("(turn >= 2) or missing", True),
])
def test_conditions(expression, expected):
    names = {"codex": {"WHERE": True}, "integrity": "damaged", "fatigue": 0.8, "turn": 3}
    assert bool(evaluate(expression, names)) is expected


def test_inline_markup_becomes_styled_tokens():
    parts = tokens("A {wave}wavy{/wave} {color gold}gold{/color} {rune WHERE} for {foe}.")
    styled = {t.text: t for t in parts if t.kind == "text"}
    assert styled["wavy"].wave and styled["gold"].color == "gold" and styled["WHERE"].rune
    assert plain("A {wave}wavy{/wave} for {foe}.") == "A wavy for {foe}."   # placeholders stay


def test_every_hint_and_dialogue_line_has_a_unique_i18n_key():
    seen: dict[str, str] = {}
    for name, script in all_scripts().items():
        for key in script.keys():
            assert key.startswith(f"story.{name}."), key
            assert key not in seen, f"{key} is used twice"
            seen[key] = name
    assert len(seen) > 100


def test_the_story_keeps_the_old_dialogue_content():
    old = legacy()
    assert old["victory"][1] == "Ada: One word. LIMIT. And the page behaves."
    assert old["battle_tip"] == "New to SQL? Press F3 for the spell guide."
    tutorial = [line["text"] for line in scene_lines("intro", {"next": "tutorial"})]
    slime = [line["text"] for line in scene_lines("intro", {"next": "slime"})]
    assert any("straw" in text for text in tutorial) and not any("straw" in t for t in slime)


# ------------------------------------------------------------------ pacing

def test_a_pause_takes_measurably_longer_in_simulated_time():
    plain_line = Typewriter("Hello there, witch.", "Ada")
    paused = Typewriter("Hello there, {pause 500}witch.", "Ada")
    assert paused.total_ms >= plain_line.total_ms + 499.9
    assert plain_line.visible(plain_line.total_ms) == len("Hello there, witch.")
    at = plain_line.times[len("Hello there,") - 1] + 1     # just after the comma...
    assert plain_line.visible(at + 50) == len("Hello there,")  # ...the comma holds the line


def test_cjk_default_speed_differs_from_latin_per_character():
    latin, cjk = Typewriter("abcdefghij", "Ada"), Typewriter("一二三四五六七八九十", "Ada")
    assert cjk.total_ms > 1.5 * latin.total_ms
    instant = Typewriter("{instant}All of it at once.", "Ada")
    assert instant.visible(0) == len("All of it at once.")
    assert Typewriter("{speed slow}abc", "Ada").total_ms > Typewriter("abc", "Ada").total_ms


def test_punctuation_pauses_are_per_language():
    english = Typewriter("一。二", "Ada", "en").total_ms
    chinese = Typewriter("一。二", "Ada", "zh-Hans").total_ms
    assert chinese > english


def test_each_speaker_has_a_voice():
    assert voice("Ada")[0] == "voice_square" and voice("Grimoire")[0] == "voice_triangle"
    assert voice("Ada") != voice("Sir Wherewell")


# ------------------------------------------------------------------ wrapping and the box

BOX = pygame.Rect(8, 128, 304, 44)


def test_a_50_character_german_line_fits_the_box():
    line = "Zauberspruch prallt von meiner Relevanzbarriere ab"
    assert len(line) == 50
    rows = wrap_text(line, BOX.width - 8)
    assert len(rows) <= 4 and all(measure(row) <= BOX.width - 8 for row in rows)
    assert not DialogueBox(BOX, rows=4).overflows(tokens(line))


def test_a_cjk_line_wraps_by_character_and_keeps_punctuation_off_the_line_start():
    line = "我是過濾騎士，我的相關性結界會擋住每一個不重要的法術。你知道是哪一個嗎？"
    rows = wrap_text(line, 60)
    assert "".join(rows) == line                         # no character lost or added
    assert len(rows) > 3 and all(measure(row) <= 60 for row in rows)
    assert not any(row[0] in "，。？" for row in rows)
    assert not any(" " in row for row in rows)


def test_latin_breaks_between_words_without_hyphens():
    rows = wrap_text("Halt! I am Sir Wherewell, Knight of the Filter.", 80)
    assert all(not row.endswith("-") for row in rows)
    assert " ".join(rows) == "Halt! I am Sir Wherewell, Knight of the Filter."


def test_an_overlong_line_never_draws_outside_its_box():
    canvas = pygame.Surface((320, 180))
    canvas.fill((1, 2, 3))
    box = DialogueBox(BOX, rows=4)
    words = tokens("A translation far longer than the box was ever meant to hold. " * 8)
    assert box.overflows(words)
    for shown in (40, 200, 10 ** 6):                     # early, midway, the whole line
        canvas.fill((1, 2, 3))
        box.draw(canvas, "", words, shown, now=500)
        for x in range(0, 320, 2):
            for y in range(0, 180, 2):
                if not BOX.collidepoint(x, y):
                    assert canvas.get_at((x, y))[:3] == (1, 2, 3), (shown, x, y)


def test_a_long_line_scrolls_so_the_newest_text_is_on_screen():
    canvas = render.Canvas((320, 180)) if hasattr(render, "Canvas") else None
    if canvas is None:
        pytest.skip("no text-layer canvas")
    box = DialogueBox(BOX, rows=4)
    words = tokens(" ".join(f"word{i}" for i in range(120)))
    box.draw(canvas, "", words, 10 ** 6, now=0)
    drawn = "".join(op[1] for op in canvas.ops if op[0] == "text")
    assert "word119" in drawn and "word0 " not in drawn
    assert all(BOX.collidepoint(op[2], op[3]) for op in canvas.ops if op[0] == "text")


# ------------------------------------------------------------------ the dialogue scene

def story(guardian="slime", audio=None):
    game = Game(pygame.Surface((320, 180)), seed=1, audio=audio or Recorder())
    game.switch(DialogueScene(game, "intro", guardian))
    return game


def test_the_scene_types_by_time_and_enter_finishes_then_advances():
    game = story()
    scene = game.scene
    run(game, 2 * scene.FADE_MS + 160)
    shown = scene._shown_chars()
    assert 0 < shown < len(scene.line["text"])
    key(game, pygame.K_RETURN)
    assert scene._line_done() and scene.index == 0
    key(game, pygame.K_RETURN)
    assert scene.index == 1


def test_holding_enter_types_faster_and_ctrl_skips():
    slow, fast = story(), story()
    run(slow, 1500)
    fast.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    fast.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN, mod=0))
    key(fast, pygame.K_RETURN)                         # on to line 2
    fast.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))   # held
    before = fast.scene.index
    run(fast, 400)
    assert fast.scene._line_done() and fast.scene.index == before   # fast, but it waits
    skip = story()
    skip.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LCTRL, mod=0))
    run(skip, 6000)
    assert skip.scene is not None and (not isinstance(skip.scene, DialogueScene)
                                       or skip.scene.index > 3)


def test_auto_advance_moves_on_by_itself_and_the_log_remembers():
    game = story()
    key(game, pygame.K_a)
    assert game.scene.auto and game.auto_advance
    run(game, 9000)
    assert game.scene.index >= 2
    said = [text for _, text in game.dialogue_log]
    assert said[0].startswith("11:58 pm")
    key(game, pygame.K_l)
    assert game.scene.show_log
    index = game.scene.index
    run(game, 3000)
    assert game.scene.index == index                   # the story waits while the log is open
    key(game, pygame.K_x)
    assert not game.scene.show_log


def test_speakers_blip_with_their_voice():
    audio = Recorder()
    game = story(audio=audio)
    for _ in range(5):
        key(game, pygame.K_RETURN)
        key(game, pygame.K_RETURN)
    run(game, 3000)
    assert ("voice_square", voice("Ada")[1]) in audio.log or \
        ("voice_triangle", voice("Grimoire")[1]) in audio.log


def test_a_choice_waits_for_the_player():
    import story.script as script_module
    script_module._LOADED["intro"] = parse(SAMPLE.replace("== glade ==", "== intro =="), "intro")
    try:
        game = story()
        scene = game.scene
        for _ in range(3):                              # three lines, then the fourth...
            key(game, pygame.K_RETURN)
            key(game, pygame.K_RETURN)
        key(game, pygame.K_RETURN)                      # ...finished: the choice is offered
        assert scene._choosing()
        key(game, pygame.K_DOWN)
        key(game, pygame.K_RETURN)                      # "Let's go." skips the Grimoire's answer
        assert scene.line["text"] == "They walk on."
    finally:
        script_module._LOADED.pop("intro")


# ------------------------------------------------------------------ the Hint Director

class FakeReport:
    def __init__(self, sql, overflow=0, damage=0, events=()):
        self.sql, self.overflow, self.events = sql, overflow, list(events)
        self.casts = [type("C", (), {"kind": "attack", "amount": damage})()] if damage else []


def ctx(**extra):
    base = {"hp": 1.0, "mp": 1.0, "heals": 2, "ethers": 2, "integrity": "intact",
            "explain": {"mode": "opening -> careful", "intent": "careful"}}
    base.update(extra)
    return base


def wait_turn(director, turn, context, seconds=10):
    director.start_turn(turn)
    for _ in range(seconds * 4):
        if hint := director.tick(250, context):
            return hint
    return None


def test_a_lazy_battle_hears_the_expected_line_at_the_expected_turn():
    director = HintDirector("slime")
    assert wait_turn(director, 1, ctx()) is None       # turn 1: nothing to say yet
    director.observe(FakeReport("SELECT name FROM spells", overflow=3))
    hint = wait_turn(director, 2, ctx())
    assert hint.node == "slime_enemies" and hint.speaker == "Asterisk Slime"
    director.observe(FakeReport("SELECT name FROM spells", overflow=3))
    hint = wait_turn(director, 3, ctx())
    assert hint.node == "slime_overflow"               # two overflows outrank the enemies table
    hint = wait_turn(director, 4, ctx())
    assert hint.node == "grimoire_overflow_nudge" and hint.speaker == "Grimoire"
    assert wait_turn(director, 5, ctx()).node == "grimoire_overflow_shape"
    assert wait_turn(director, 6, ctx()).node == "grimoire_enemies_nudge"   # escalates


def test_one_line_per_turn_a_cooldown_and_never_the_same_line_twice():
    director = HintDirector("knight")
    director.observe(FakeReport("SELECT name FROM spells"))
    director.start_turn(2)
    lines = [h for _ in range(400) if (h := director.tick(250, ctx()))]
    assert len(lines) == 1                              # a whole turn of idling: one line
    said = [lines[0].node]
    for turn in range(3, 30):
        if hint := wait_turn(director, turn, ctx(), seconds=40):
            said.append(hint.node)
    assert len(said) == len(set(said))                  # no repeats in a fight
    assert len(said) > 3


def test_hints_wait_for_idle_time_and_typing_resets_it():
    director = HintDirector("slime")
    director.observe(FakeReport("SELECT name FROM spells"))
    director.start_turn(2)
    for _ in range(20):
        assert director.tick(250, ctx()) is None
        director.keystroke()                            # she is typing: nobody interrupts
    assert any(director.tick(250, ctx()) for _ in range(40))


def test_a_strong_player_gets_silence():
    director = HintDirector("knight")
    for turn in range(1, 8):
        director.observe(FakeReport(f"SELECT name FROM spells WHERE element = 'Tide' LIMIT {turn}",
                                    damage=12))
        director.signals.seen.add("enemies")
        assert wait_turn(director, turn + 1, ctx(hp=0.8)) is None


def test_loud_topics_speak_even_to_a_strong_player():
    director = HintDirector("slime")
    director.observe(FakeReport("DELETE FROM enemies", damage=5))
    hint = wait_turn(director, 2, ctx(integrity="damaged"), seconds=1)
    assert hint.node == "slime_world"
    assert "put it back" in hint.text


@pytest.mark.parametrize("guardian, mode, words", [
    ("slime", "careful", "careful"), ("slime", "overcast", "greedy"),
    ("knight", "pressing", "on the attack"), ("knight", "besieged", "besieged"),
])
def test_the_guardians_taunt_matches_its_explain(guardian, mode, words):
    director = HintDirector(guardian)
    for turn in (1, 2, 3):
        director.observe(FakeReport("SELECT name FROM spells WHERE 1"))
    explain = {"mode": f"vigilant -> {mode}", "intent": "strike"}
    hint = wait_turn(director, 4, ctx(explain=explain))
    assert hint.node == f"{guardian}_habit"
    assert mode_of(explain) == mode and words in hint.text


def test_the_taunt_is_truthful_in_a_real_battle():
    battle = Battle(seed=2, guardian="knight", foe_opens=True)
    battle.foe_act()
    director = HintDirector("knight")
    for _ in range(3):
        director.observe(FakeReport("SELECT name FROM spells"))
    hint = wait_turn(director, battle.state.turn, context_of(battle))
    mode = mode_of(battle.brain.explain())
    assert hint.node == "knight_habit"
    assert hints_module.CATALOG.raw(f"hint.mode.{mode}") in hint.text


def test_low_hp_with_an_unused_herb_and_low_mp_with_an_unused_ether():
    director = HintDirector("slime")
    director.signals.seen |= {"enemies", "items"}
    assert wait_turn(director, 2, ctx(hp=0.2)).node == "slime_heal"
    assert wait_turn(director, 3, ctx(hp=0.2)).node == "grimoire_heal_shape"
    director.observe(FakeReport("SELECT name FROM items WHERE name = 'Ether'",
                                events=[("item", 0, "Ether", "Ada", "mp", 10)]))
    assert wait_turn(director, 4, ctx(mp=0.1)) is None  # she already knows the Ether


def test_every_hint_node_the_data_names_exists():
    data = hints_module.settings()
    nodes = hints_module.get(data["script"]).nodes
    pools = {"slime": 0, "knight": 0, "grimoire": 0}
    for topic in data["topics"]:
        for step in topic["steps"]:
            for guardian in ("slime", "knight"):
                assert step.replace("{guardian}", guardian) in nodes
    for node in nodes:
        pools[node.split("_")[0]] += 1
    assert pools == {"slime": 8, "knight": 8, "grimoire": 12}


def test_the_battle_scene_speaks_a_hint_when_ada_is_stuck():
    game = Game(pygame.Surface((320, 180)), seed=1, audio=Recorder())
    scene = BattleScene(game, "slime")
    game.switch(scene)
    scene.hints.signals.miscasts = 2                  # she has miscast twice in a row
    for _ in range(1500):                             # the Slime acts first, then she is stuck
        game.update(16)
        game.draw()
        if scene.beat is not None and scene.beat.markup:
            break
    assert scene.beat.speaker in ("Asterisk Slime", "Grimoire")
    assert scene.hints.log
