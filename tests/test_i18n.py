"""Prompt 04: catalogs, plurals and gender, fonts, overflow, input, runtime language switch."""

import ast
import json
import re
from pathlib import Path

import pytest

pygame = pytest.importorskip("pygame")

from engine import fonts, render  # noqa: E402
from engine.scenes import BattleScene, DialogueScene, Game, TitleScene  # noqa: E402
from engine.textinput import QueryEditor  # noqa: E402
from i18n import CATALOG, check, set_locale, t  # noqa: E402
from i18n.catalog import Catalog  # noqa: E402
from i18n.icu import format_message, plural_category  # noqa: E402
from i18n.pseudo import pseudo  # noqa: E402
from i18n.width import cells, text_cells, wrap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module", autouse=True)
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def english_after():
    yield
    set_locale("en")
    CATALOG.set_player(name="Ada", gender="feminine")


def key(game, k, mod=0):
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))
    game.handle(pygame.event.Event(pygame.KEYUP, key=k, mod=mod))


def run(game, ms):
    for _ in range(ms // 16):
        game.update(16)
        game.draw()


# ------------------------------------------------------------------ plurals and gender

# CLDR plural categories, for 0 1 2 3 5 7 11 12 21 22 101 1000000 and 1.5, per language.
N = (0, 1, 2, 3, 5, 7, 11, 12, 21, 22, 101, 1000000, 1.5)
CLDR = {
    "en": "other one other other other other other other other other other other other",
    "es": "other one other other other other other other other other other many other",
    "zh-Hans": " ".join(["other"] * 13), "zh-Hant": " ".join(["other"] * 13),
    "id": " ".join(["other"] * 13),
    "bg": "other one other other other other other other other other other other other",
    "hr": "other one few few other other other other one few one other other",
    "cs": "other one few few other other other other other other other other many",
    "sk": "other one few few other other other other other other other other many",
    "da": "other one other other other other other other other other other other one",
    "nl": "other one other other other other other other other other other other other",
    "et": "other one other other other other other other other other other other other",
    "fi": "other one other other other other other other other other other other other",
    "de": "other one other other other other other other other other other other other",
    "el": "other one other other other other other other other other other other other",
    "hu": "other one other other other other other other other other other other other",
    "sv": "other one other other other other other other other other other other other",
    "fr": "one one other other other other other other other other other many one",
    "it": "other one other other other other other other other other other many other",
    "pt": "one one other other other other other other other other other many one",
    "ga": "other one two few few many other other other other other other other",
    "lv": "zero one other other other other zero zero one other one zero other",
    "lt": "other one few few few few other other one few one other many",
    "mt": "few one two few few few many many other other other other other",
    "pl": "many one few few many many many many many few many many other",
    "ro": "few one few few few few few few other other few other few",
    "sl": "other one two few other other other other other other one other few",
}


def test_every_target_language_is_listed_once():
    listed = set(CATALOG.settings()["locales"]) - {"qps"}
    assert listed == set(CLDR) and len(listed) == 27


@pytest.mark.parametrize("locale", sorted(CLDR))
def test_cldr_plural_categories(locale):
    assert [plural_category(n, locale) for n in N] == CLDR[locale].split()


def test_plural_messages_pick_the_language_form():
    message = "{count, plural, one {# fila} few {# řádky} many {# wierszy} other {# rows}}"
    assert format_message(message, {"count": 1}, "es") == "1 fila"
    assert format_message(message, {"count": 3}, "cs") == "3 řádky"
    assert format_message(message, {"count": 5}, "pl") == "5 wierszy"
    assert format_message("{n, plural, =0 {none} other {# left}}", {"n": 0}, "en") == "none"


def test_without_babel_plurals_fall_back_to_english_instead_of_crashing(monkeypatch, capsys):
    import sys

    from i18n import icu
    monkeypatch.setitem(sys.modules, "babel", None)        # as if it were not installed
    icu._plural_rule.cache_clear()
    try:
        assert t("battle.margin", count=1) == "1 spell fizzles in the margin"
        assert t("battle.margin", count=4) == "4 spells fizzle in the margin"
        assert "pip install -r requirements.txt" in capsys.readouterr().out
    finally:
        icu._plural_rule.cache_clear()


def test_gender_select_on_the_player():
    line = "{player.gender, select, feminine {la bruja} masculine {el brujo} other {x}}"
    assert CATALOG.format(line) == "la bruja"
    CATALOG.set_player(gender="masculine")
    assert CATALOG.format(line) == "el brujo"
    set_locale("es")
    assert "brujo" in t("story.intro.knight_intro.4") and "bruja" not in \
        t("story.intro.knight_intro.4")
    CATALOG.set_player(gender="feminine")
    assert "bruja" in t("story.intro.knight_intro.4")


def test_the_player_name_fills_every_message():
    CATALOG.set_player(name="Lin")
    assert t("miscast.empty").startswith("Lin:")
    from story.scenes import scene_lines
    assert any("Lin" in line["text"] for line in scene_lines("intro", {"next": "slime"}))


def test_gendered_entries_are_counted_per_language():
    assert check.gendered("es") >= 10 and check.gendered("zh-Hans") == 0


# ------------------------------------------------------------------ catalogs

def code_keys() -> set[str]:
    """Every key the code asks for with a literal string: t("...") and CATALOG.raw("...")."""
    found = set()
    for package in ("engine", "magic", "story", "ai", "sim", "i18n", "save"):
        for path in (ROOT / package).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and node.args and \
                        isinstance(node.args[0], ast.Constant) and \
                        isinstance(node.args[0].value, str):
                    name = node.func.attr if isinstance(node.func, ast.Attribute) else \
                        getattr(node.func, "id", "")
                    if name in ("t", "raw") and re.fullmatch(r"[a-z_]+(\.[A-Za-z_ ]+)+",
                                                             node.args[0].value):
                        found.add(node.args[0].value)
    return found


def test_every_key_used_in_code_exists_in_english():
    keys = code_keys()
    assert len(keys) > 60
    missing = sorted(k for k in keys if not CATALOG.has(k))
    assert missing == []


def test_every_key_named_in_data_exists_in_english():
    reactions = json.loads((ROOT / "data" / "reactions.json").read_text())
    named = {r["line_key"] for r in reactions["reactions"]}
    tricks = json.loads((ROOT / "data" / "tricks.json").read_text())
    named |= {r["line_key"] for r in tricks.get("tricks", []) if "line_key" in r}
    named |= {f"hint.mode.{m}" for m in ("opening", "wobble", "overcast", "exhausted", "careful",
                                         "vigilant", "pressing", "besieged", "winded", "desperate")}
    assert all(CATALOG.has(k) for k in named), [k for k in named if not CATALOG.has(k)]


@pytest.mark.parametrize("locale", ["es", "zh-Hans", "zh-Hant"])
def test_launch_languages_are_complete_and_keep_their_placeholders(locale):
    assert check.untranslated(locale) == []
    from tools.translate import check as placeholders
    assert placeholders(locale) == []


def test_menu_lists_reviewed_and_preview_languages_but_not_qps(tmp_path):
    menu = CATALOG.menu_locales()
    assert menu[:4] == ["en", "es", "zh-Hans", "zh-Hant"] and "qps" not in menu
    assert "qps" in CATALOG.menu_locales(include_pseudo=True)
    assert CATALOG.is_draft("es") and not CATALOG.is_draft("en")
    # A language a reviewer signed off reaches the menu without being in preview.
    (tmp_path / "en.json").write_text(json.dumps({"a": "one", "b": "two"}))
    (tmp_path / "fr.json").write_text(json.dumps({"a": "un", "b": "deux",
                                                  "_status": {"a": "reviewed", "b": "reviewed"}}))
    (tmp_path / "de.json").write_text(json.dumps({"a": "eins", "_status": {"a": "reviewed"}}))
    (tmp_path / "locales.json").write_text(json.dumps(
        {"review_threshold": 1.0, "preview": [], "pseudo": "qps",
         "locales": {"en": {}, "fr": {}, "de": {}, "qps": {}}}))
    catalog = Catalog(tmp_path)
    catalog._status["_settings"] = json.loads((tmp_path / "locales.json").read_text())
    catalog._cache["en"] = {"a": "one", "b": "two"}          # no scripts in this folder
    assert catalog.menu_locales() == ["en", "fr"]


def test_translate_never_overwrites_a_reviewed_entry_and_refuses_broken_lines(tmp_path,
                                                                              monkeypatch):
    import shutil

    import tools.translate as translate
    for name in ("en.json", "locales.json", "es.json"):
        shutil.copy(ROOT / "data" / "i18n" / name, tmp_path / name)
    monkeypatch.setattr(translate, "CATALOG_DIR", tmp_path)
    data = translate.load("es")
    data["_status"]["title.press_enter"] = "reviewed"
    translate.save("es", data)
    written, refused = translate.write_drafts("es", {
        "title.press_enter": "otra cosa",                   # reviewed: kept
        "title.seed": "semilla",                           # lost {seed}: refused
        "result.victory": "¡VICTORIA!"})
    after = translate.load("es")
    assert after["title.press_enter"] == "pulsa ENTER" and written == 1
    assert any("title.seed" in r for r in refused) and after["result.victory"] == "¡VICTORIA!"
    CATALOG.reload()


# ------------------------------------------------------------------ the pseudo-locale

def test_pseudo_accents_lengthens_and_keeps_sql_and_placeholders():
    text = "Look first: SELECT * FROM enemies. {count, plural, one {# row} other {# rows}} {foe}"
    out = pseudo(text)
    shown = format_message(out, {"count": 3, "foe": "X"}, "en")
    plain_en = format_message(text, {"count": 3, "foe": "X"}, "en")
    assert out.startswith("[") and out.endswith("]") and len(shown) >= 1.3 * len(plain_en)
    assert "SELECT * FROM enemies" in out and "{foe}" in out and "Look" not in out
    assert format_message(out, {"count": 1, "foe": "X"}, "en").count("X") == 1


ALLOWED = re.compile(r"^[\s\d\W]*$")


def schema_words() -> set[str]:
    from magic.battle import Battle
    battle = Battle(seed=1)
    words = set()
    for (table,) in battle.conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        words.add(table.lower())
        words |= {r[1].lower() for r in battle.conn.execute(f"PRAGMA table_info({table})")}
    return words


def test_a_qps_playthrough_shows_no_text_from_code():
    """Every frame of a scripted run in qps: a word of plain English outside [brackets] can
    only be data (table and column names, SQL, values), never interface text."""
    set_locale("qps")
    allowed = schema_words() | {"attack", "dispel", "relevance", "ward", "heal", "area"}
    seen: set[str] = set()
    canvas = render.Canvas()
    game = Game(canvas, seed=2, start="slime")
    run(game, 300)
    key(game, pygame.K_RETURN)
    for _ in range(40):
        if not isinstance(game.scene, DialogueScene):
            break
        run(game, 150)
        seen |= set(canvas.texts())
        key(game, pygame.K_RETURN)
    for query in ("SELECT * FROM enemies", "SELECT name FROM spells LIMIT 2", "SELEC oops"):
        scene = game.scene
        for _ in range(200):
            if getattr(scene, "phase", "") == "input":
                break
            run(game, 50)
            seen |= set(canvas.texts())
        for char in query:
            game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))
        key(game, pygame.K_RETURN, pygame.KMOD_CTRL)
        run(game, 1500)
        seen |= set(canvas.texts())
    key(game, pygame.K_F3)
    run(game, 100)
    seen |= set(canvas.texts())
    bad = []
    for text in seen:
        outside = re.sub(r"\[[^\]]*\]?", "", text)
        words = {w.lower() for w in re.findall(r"\b[a-z]{3,}\b", outside)}
        if words - allowed - {"such", "table", "column", "near", "syntax", "error", "oops",
                              "selec", "enemiesselec", "incomplete", "input"}:
            bad.append(text)
    assert bad == []


# ------------------------------------------------------------------ fitting the boxes

@pytest.mark.parametrize("locale", ["en", "es", "zh-Hans", "zh-Hant"])
def test_every_string_fits_its_box(locale):
    assert locale in CATALOG.menu_locales()
    assert check.overflows(locale) == []


def test_a_cjk_character_takes_two_cells_and_wraps_alone():
    assert cells("中") == 2 and cells("a") == 1 and text_cells("SQL 中文") == 8
    rows = wrap("这是一个很长的中文句子，用来测试换行。", 10)
    assert all(text_cells(r) <= 10 for r in rows) and not any(r[0] in "，。" for r in rows)


# ------------------------------------------------------------------ fonts

EU_LETTERS = ("áàâäãåāăąćčçďđéèêëēėęěíìîïīįĺľłńňñóòôöõőøōŕřśšşșťţțúùûüűūůųýÿźžżßæœħġċ"
              "ÁÀÂÄÃÅĀĂĄĆČÇĎĐÉÈÊËĒĖĘĚÍÌÎÏĪĮĹĽŁŃŇÑÓÒÔÖÕŐØŌŔŘŚŠŞȘŤŢȚÚÙÛÜŰŪŮŲÝŸŹŽŻÆŒĦĠĊ"
              "¿¡«»„“”‘’…–€")


def test_every_eu_latin_letter_has_a_pixel_glyph():
    missing = [c for c in EU_LETTERS if fonts.composed(c) is None]
    assert missing == []


def test_greek_and_cyrillic_and_chinese_come_from_unifont():
    for char in "ΑλφαБългарски中文繁體":
        assert fonts.composed(char) is None and fonts.unifont_has(char)


@pytest.mark.parametrize("locale", ["zh-Hans", "zh-Hant", "es"])
def test_every_character_of_a_catalog_can_be_drawn(locale):
    chars = {c for text in CATALOG.messages(locale).values() for c in text}
    assert sorted(c for c in chars if not fonts.covered(c)) == []


def test_mixed_scripts_render_per_run_at_2x():
    canvas = render.Canvas()
    canvas.fill(render.CREAM)
    render.font().draw(canvas, "Ada 你好 Ωμέγα ñ", (4, 20), render.INK)
    k = 2
    frame = pygame.transform.scale(canvas, (320 * k, 180 * k))
    render.draw_text_layer(frame, canvas.ops, k)
    col = 0
    for char in "Ada 你好 Ωμέγα ñ":
        width = cells(char) * render.ADVANCE * k
        area = pygame.Rect((4 + col * render.ADVANCE) * k, 20 * k - 4, width, render.LINE_H * k + 6)
        inked = sum(1 for x in range(area.x, area.right) for y in range(area.y, area.bottom)
                    if frame.get_at((x, y))[:3] != render.CREAM)
        assert (inked > 0) == (char != " "), char
        col += cells(char)
    assert render.font().width("你好") == 4 * render.ADVANCE - 1


# ------------------------------------------------------------------ input

def test_ime_composition_shows_inline_and_commits():
    editor = QueryEditor(names=[], tables=[], unlocked=set())
    editor.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="SELECT '"))
    editor.handle_event(pygame.event.Event(pygame.TEXTEDITING, text="huo", start=3, length=0))
    canvas = render.Canvas()
    editor.draw(canvas, (10, 10), 0)
    assert "huo" in canvas.texts() and editor.text == "SELECT '"
    editor.handle_event(pygame.event.Event(pygame.TEXTEDITING, text="火", start=1, length=0))
    editor.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="火"))
    assert editor.text == "SELECT '火" and editor.composing == ""
    x, _ = editor.cursor_xy((10, 10))
    assert x == 10 + (len("SELECT '") + 2) * render.ADVANCE        # the wide character


def test_query_characters_come_from_text_events_not_key_codes():
    """A French or German keyboard types * = ' ; < > ( ) on other keys: only TEXTINPUT adds
    characters, key events only edit."""
    editor = QueryEditor(names=[], tables=[], unlocked=set())
    editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_8, mod=0, unicode="*"))
    assert editor.text == ""
    for char in "*=';<>()":
        editor.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=char))
    assert editor.text == "*=';<>()"


# ------------------------------------------------------------------ switching at runtime

def test_switching_language_re_renders_every_open_scene():
    canvas = render.Canvas()
    game = Game(canvas, seed=1, start="slime")
    game.draw()
    assert t("title.subtitle") in canvas.texts()
    key(game, pygame.K_l)                                    # L: the next language
    assert CATALOG.locale == "es"
    game.draw()
    assert "un RPG por turnos donde tus consultas son hechizos" in canvas.texts()
    key(game, pygame.K_RETURN)
    assert isinstance(game.scene, DialogueScene)
    first = game.scene.line["text"]
    set_locale("zh-Hans")
    assert game.scene.line["text"] != first and "季度报表" in game.scene.line["text"]
    battle = BattleScene(game, "slime")
    game.switch(battle)
    run(game, 50)
    assert "你的查询" in canvas.texts()
    set_locale("en")
    run(game, 50)
    assert "YOUR QUERY" in canvas.texts()


def test_title_shows_the_language_and_its_draft_mark():
    canvas = render.Canvas()
    game = Game(canvas, seed=1)
    set_locale("es")
    game.draw()
    assert any("Español (borrador)" in text for text in canvas.texts())
    assert isinstance(game.scene, TitleScene)


def test_main_accepts_a_locale(capsys):
    import main
    assert main.main(["--locale", "xx", "--smoke-test"]) == 2
    assert main.main(["--locale", "qps", "--smoke-test"]) == 0
