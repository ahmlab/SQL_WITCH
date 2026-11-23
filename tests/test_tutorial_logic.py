"""The tutorial's lesson logic (magic/tutorial.py), headless: no pygame anywhere in here."""

import copy
import json

import pytest

from magic.db import DATA_DIR, build_db
from magic.tutorial import (DUMMY_CHARS, STRIP_CHARS, Tutorial, ghost_text, goal_met,
                            load_script, script_problems, wrap)

SCRIPT = load_script()
LESSONS = [lesson["id"] for lesson in SCRIPT["lessons"]]


def to_task(t: Tutorial, lesson_id: str | None = None) -> Tutorial:
    """Click through the talk (and the Grimoire's demos) until the player has to write.
    With a lesson id, pass the lessons before it with their own example queries."""
    while True:
        while t.phase != "task":
            if t.phase == "demo":
                t.cast_demo()
            elif t.phase == "done":
                return t
            else:
                t.advance()
        if lesson_id is None or t.lesson["id"] == lesson_id:
            return t
        assert t.cast(t.lesson["example"]).kind == "pass"


def tutorial(lesson_id: str | None = None, seed: int = 1) -> Tutorial:
    return to_task(Tutorial(seed=seed), lesson_id)


def finish(t: Tutorial) -> Tutorial:
    """Play the rest of the tutorial with the examples, then READY and the ending."""
    while not t.done:
        to_task(t)
        if t.done:
            break
        if t.practising:
            assert t.ready()
        else:
            assert t.cast(t.lesson["example"]).kind == "pass"
    return t


# ------------------------------------------------------------------ the script

def test_the_script_loads_and_every_line_fits_its_box():
    assert script_problems(SCRIPT) == []


def test_a_line_that_does_not_fit_is_refused_with_its_place():
    script = copy.deepcopy(SCRIPT)
    script["lessons"][0]["intro"][0]["say"] = "word " * 40
    problems = script_problems(script)
    assert problems and problems[0].startswith("look.intro[0].say")


def test_unknown_goals_highlights_and_reveals_are_refused():
    script = copy.deepcopy(SCRIPT)
    script["lessons"][0]["goal"]["is_fun"] = True
    script["lessons"][0]["intro"][0]["point"] = "the_moon"
    script["lessons"][0]["reveal"] = ["everything"]
    problems = " ".join(script_problems(script))
    assert "is_fun" in problems and "the_moon" in problems and "everything" in problems


def test_the_wrap_here_is_the_one_the_screen_uses():
    pygame = pytest.importorskip("pygame")          # only to import the engine's twin
    from engine.grimoire import wrap as screen_wrap
    texts = [s["say"] for lesson in SCRIPT["lessons"] for key in ("intro", "demo_after", "success")
             for s in lesson.get(key, [])]
    for text in texts:
        for width in (STRIP_CHARS, DUMMY_CHARS):
            assert wrap(text, width) == screen_wrap(text, width)


def test_the_script_never_teaches_a_rune():
    text = json.dumps({k: v for k, v in SCRIPT.items() if k != "_help"})
    for rune in ("LIMIT", "WHERE", "ORDER BY", "JOIN"):
        assert rune not in text.replace("{rune}", "")
    for lesson in SCRIPT["lessons"]:
        assert set(lesson["example"].upper().split()) & {"LIMIT", "WHERE"} == set()


def test_the_dummy_is_one_new_row_weak_to_fire_with_no_spells():
    conn = build_db(foe_ids=[3])
    assert conn.execute("SELECT name, weakness FROM enemies").fetchall() == \
        [("Training Dummy", "Fire")]
    assert conn.execute("SELECT COUNT(*) FROM foe_spells").fetchone() == (0,)
    full = build_db()
    assert full.execute("SELECT COUNT(*) FROM enemies").fetchone() == (3,)


# ------------------------------------------------------------------ the flow

def test_the_tutorial_opens_with_the_grimoire_then_a_demo_of_the_same_query():
    t = Tutorial(seed=1)
    assert t.phase == "opening" and t.step.say and t.step.dummy
    t.advance()
    assert t.phase == "intro" and t.lesson["id"] == "look"
    while t.phase == "intro":
        t.advance()
    assert t.phase == "demo" and t.demo_query == t.lesson["example"]
    report = t.cast_demo()
    assert report.sql == "SELECT * FROM enemies" and report.scry
    assert t.phase == "after" and t.step.point == "row:0"


def test_a_scripted_player_finishes_with_exactly_the_runes_ada_had():
    t = finish(tutorial())
    assert t.done and t.passed == LESSONS
    assert t.battle.state.ada.runes == set()        # the Slime still teaches LIMIT
    assert [r["lesson"] for r in t.records] == LESSONS + ["practice"]
    assert all(r["result"] == "passed" for r in t.records[:-1])
    assert t.records[-1]["result"] == "ready"


def test_ready_only_works_in_free_practice():
    t = tutorial("look")
    assert not t.ready()
    t = tutorial("practice")
    assert t.practising and t.ready() and t.phase == "ending"


def test_skip_ends_at_once_and_is_recorded():
    t = tutorial("columns")
    t.skip()
    assert t.done and t.records[-1]["lesson"] == "columns"
    assert t.records[-1]["result"] == "skipped"


def test_lessons_reveal_the_screen_little_by_little():
    t = tutorial("look")
    assert t.revealed == set()
    t = tutorial("read")
    assert "ada_panel" in t.revealed and "tables_button" not in t.revealed
    t = tutorial("practice")
    assert {"looks", "tables_button", "status", "foe_panel"} <= t.revealed
    assert "guide_button" not in t.revealed
    t.ready()
    while not t.done:
        t.advance()
    assert "guide_button" in t.revealed             # the very last thing shown


# ------------------------------------------------------------------ judging the result

@pytest.mark.parametrize("lesson, sql", [
    ("look", "SELECT * FROM enemies"),
    ("look", "select name, hp from enemies"),
    ("look", "SELECT weakness FROM enemies"),
    ("columns", "SELECT name, weakness FROM enemies"),
    ("columns", "SELECT weakness FROM enemies"),
    ("columns", "select element, weakness from enemies"),
    ("read", "SELECT element, power, mp_cost FROM spells"),
    ("read", "SELECT element FROM spells"),
    ("read", "SELECT kind, element FROM spells"),
    ("cast", "SELECT name FROM spells"),
    ("cast", "SELECT name, element FROM spells"),
    ("cast", "SELECT * FROM spells"),
])
def test_any_query_that_meets_the_goal_passes(lesson, sql):
    t = tutorial(lesson)
    assert t.cast(sql).kind == "pass"
    assert t.phase == "success"


@pytest.mark.parametrize("lesson, sql, kind", [
    ("look", "SELECT * FROM witch", "off_goal"),
    ("columns", "SELECT * FROM enemies", "off_goal"),          # weakness is cut off the page
    ("columns", "SELECT hp AS weakness FROM enemies", "off_goal"),   # a renamed column
    ("columns", "SELECT name, weakness FROM spells", "miscast"),
    ("read", "SELECT power, mp_cost FROM spells", "off_goal"),
    ("read", "SELECT * FROM spells", "early_cast"),            # names fire spells
    ("cast", "SELECT name FROM items", "off_goal"),            # potions are not spells
    ("cast", "SELECT element FROM spells", "off_goal"),
])
def test_an_off_goal_query_is_shown_and_coached_not_passed(lesson, sql, kind):
    t = tutorial(lesson)
    outcome = t.cast(sql)
    assert outcome.kind == kind and t.phase == "task" and t.lesson["id"] == lesson
    assert t.strip().write == t.lesson["example"]             # always: what to type next
    if kind != "miscast":
        assert outcome.report is not None                    # the result is still shown


def test_nothing_is_locked_any_more_and_the_codex_remembers():
    # Sandbox v2: LIMIT is not a lock. Using it before the Slime simply works, and the Codex
    # records the player's first query with it.
    t = tutorial("cast")
    assert t.cast("SELECT name FROM spells LIMIT 1").kind == "pass"
    assert t.battle.codex.pages["LIMIT"].first_query == "SELECT name FROM spells LIMIT 1"


def test_in_practice_whatever_a_query_breaks_is_put_back():
    t = tutorial("look")
    outcome = t.cast("DROP TABLE enemies")
    assert outcome.kind == "undone" and t.phase == "task"
    assert "put it back" in t.strip().say and t.strip().write == "SELECT * FROM enemies"
    conn = t.battle.conn
    assert conn.execute("SELECT name FROM enemies").fetchone() == ("Training Dummy",)
    assert t.cast("SELECT * FROM enemies").kind == "pass"     # the lesson goes on


def test_a_miscast_keeps_the_games_humour_and_ends_with_what_to_type():
    t = tutorial("look")
    outcome = t.cast("ATTACH 'outside.db' AS outside")
    assert outcome.kind == "miscast" and outcome.message.startswith("Ada:")
    assert t.strip().write == "SELECT * FROM enemies"
    assert outcome.dummy                                     # and the dummy has an opinion


def test_enter_on_a_finished_query_teaches_the_cast_key():
    t = tutorial("look")
    assert not t.on_enter("SELECT *")
    assert t.on_enter("SELECT * FROM enemies")
    assert "CTRL+ENTER" in t.strip().say


def test_goals_are_judged_on_the_report():
    t = tutorial("columns")
    report = t.battle.ada_cast("SELECT weakness, name FROM enemies")
    assert goal_met({"look": True, "from": "enemies", "visible": ["weakness"]}, report)
    assert not goal_met({"spells_cast": 1}, report)
    assert not goal_met({"from": "spells"}, report)


# ------------------------------------------------------------------ no stakes

def test_ada_never_loses_hp_and_every_task_starts_with_full_mp():
    t = Tutorial(seed=4)
    ada = t.battle.state.ada
    while not t.done:
        to_task(t)
        if t.done:
            break
        assert ada.hp == ada.max_hp and ada.mp == ada.max_mp
        if t.practising:
            for sql in ("SELECT name FROM spells", "SELECT * FROM witch", "SELECT name FROM items"):
                t.cast(sql)
                assert ada.hp == ada.max_hp and ada.mp == ada.max_mp
            t.ready()
        else:
            t.cast("SELECT name FROM spells")                 # cast at the dummy, any lesson
            assert ada.hp == ada.max_hp
            if t.phase == "task":
                t.cast(t.lesson["example"])
    assert ada.hp == ada.max_hp


def test_the_dummy_restuffs_itself_and_never_falls():
    t = tutorial("cast")
    dummy = t.battle.state.foe
    outcome = t.cast("SELECT name FROM spells")
    assert outcome.restuffed and dummy.hp == dummy.max_hp and t.battle.winner is None


def test_the_overflow_numbers_come_from_the_real_result():
    t = tutorial("cast")
    report = t.cast("SELECT name FROM spells").report
    lines = []
    while t.phase == "success":
        lines.append(t.step.say)
        t.advance()
    told = " ".join(lines)
    assert f"{len(report.casts)} hit, {report.overflow} fizzled, {len(report.rows)} paid" in told


def test_the_cast_lesson_refills_the_mana_visibly():
    t = Tutorial(seed=1)
    to_task(t, "cast")
    assert t.battle.state.ada.mp == t.battle.state.ada.max_mp
    t.cast("SELECT name FROM spells")
    assert t.battle.state.ada.mp == 0                       # the overflow drained it...
    refills = []
    while t.phase == "success":
        refills.append(t.step.refill)
        t.advance()
    assert any(refills) and t.battle.state.ada.mp == t.battle.state.ada.max_mp   # ...on screen


def test_looks_never_run_out_during_a_lesson():
    t = tutorial("look")
    for _ in range(6):
        outcome = t.cast("SELECT * FROM witch")
        assert outcome.report.scry and not outcome.report.ends_turn


def test_the_dummy_never_touches_the_battles_rng():
    a, b = tutorial("cast", seed=9), tutorial("cast", seed=9)
    assert a.battle.rng.random() == b.battle.rng.random()
    a.cast("SELECT name FROM spells"), b.cast("SELECT name FROM spells")
    assert [c.damage for c in a.last_report.casts] == [c.damage for c in b.last_report.casts]


# ------------------------------------------------------------------ nobody stays stuck

def test_idle_time_climbs_the_hint_ladder_one_step_at_a_time():
    t = tutorial("cast")
    limits = SCRIPT["hints"]["idle_ms"]
    assert t.hint_level == 0 and t.ghost_mode == "none"
    t.tick(limits[0])
    assert t.hint_level == 1 and t.strip().write == "SELECT name FROM spells"
    t.tick(limits[1] - limits[0])
    assert t.hint_level == 2 and t.ghost_mode == "word"
    assert t.next_step("") == ("SELECT", "")                  # one word at a time
    t.tick(limits[2] - limits[1])
    assert t.hint_level == 3 and t.ghost_mode == "full"
    assert "TAB" in t.strip().say
    assert t.next_step("")[0] == "SELECT name FROM spells"


def test_typing_resets_the_idle_clock_but_never_lowers_the_level():
    t = tutorial("read")
    t.tick(SCRIPT["hints"]["idle_ms"][0] - 1)
    t.activity()
    t.tick(SCRIPT["hints"]["idle_ms"][0] - 1)
    assert t.hint_level == 0
    t.tick(1)
    assert t.hint_level == 1
    t.activity()
    assert t.hint_level == 1


def test_repeated_failures_raise_the_hint_level():
    t = tutorial("columns")
    tries = SCRIPT["hints"]["failed_tries"]
    for n in range(1, tries[-1] + 1):
        t.cast("SELECT * FROM witch")
        assert t.hint_level == sum(n >= limit for limit in tries)
    assert t.hint_level == 3 and t.next_step("")[0] == "SELECT name, weakness FROM enemies"


def test_talk_does_not_count_as_being_stuck():
    t = Tutorial(seed=1)
    t.tick(10 ** 6)
    assert t.hint_level == 0


def test_the_hint_level_starts_again_in_each_lesson():
    t = tutorial("look")
    t.tick(10 ** 6)
    assert t.hint_level == 3
    t.cast(t.lesson["example"])
    to_task(t)
    assert t.lesson["id"] == "columns" and t.hint_level == 0


# ------------------------------------------------------------------ the faded text fades

def test_lesson_one_offers_the_whole_query_so_tab_and_ctrl_enter_are_enough():
    t = tutorial("look")
    insert, advice = t.next_step("")
    assert insert == "SELECT * FROM enemies" and advice == ""
    assert t.next_step(insert) == ("", SCRIPT["coach"]["cast_hint"])
    assert t.cast(insert).kind == "pass"


def test_lesson_two_offers_only_keywords():
    t = tutorial("columns")
    assert t.next_step("") == ("SELECT", "")
    assert t.next_step("SELECT ") == ("", "")                 # the columns are yours to choose
    assert t.next_step("SELECT name, weakness ") == ("FROM", "")


def test_lessons_three_and_four_offer_no_faded_text():
    for lesson in ("read", "cast"):
        t = tutorial(lesson)
        assert t.next_step("") == ("", "")
    assert tutorial("read").strip().hint                      # lesson 3: a hint line only


@pytest.mark.parametrize("typed, expected", [
    ("", "SELECT * FROM enemies"),
    ("SEL", "ECT * FROM enemies"),
    ("select * ", "from enemies"),
    ("SELECT * FROM enemies", ""),
    ("SELECT * FROM witch", ""),          # off the path: no guessing
])
def test_the_ghost_follows_the_player_on_the_example(typed, expected):
    assert ghost_text("SELECT * FROM enemies", typed, "full")[0] == expected


# ------------------------------------------------------------------ free practice and records

def test_quests_are_checked_on_the_result_and_counted_once():
    t = tutorial("practice")
    assert t.cast("SELECT element FROM witch").quest == "element"
    assert t.cast("SELECT name, element FROM witch").kind == "free"
    assert t.cast("SELECT * FROM foe_spells").quest == "book"
    assert t.cast("SELECT sql FROM query_log").quest == "log"
    assert t.quests_done == ["element", "book", "log"]
    assert t.strip().say == SCRIPT["practice"]["quests"][2]["done"]["say"]   # its reaction...
    t.activity()                                             # ...until the next key
    assert t.strip().say == SCRIPT["practice"]["all_done"]["say"]


def test_practice_looks_do_run_out_like_in_a_real_fight():
    t = tutorial("practice")
    reports = [t.cast("SELECT * FROM witch").report for _ in range(4)]
    assert [r.ends_turn for r in reports] == [False, False, False, True]
    assert "3 free looks" in t.strip().say


def test_records_hold_what_the_playtest_log_needs():
    t = tutorial("look")
    t.tick(1500)
    t.cast("ATTACH 'outside.db' AS outside")
    t.cast("SELECT * FROM witch")
    t.cast("SELECT * FROM enemies")
    while t.phase == "success":
        t.advance()
    record = t.records[0]
    assert record["lesson"] == "look" and record["result"] == "passed"
    assert record["miscasts"] == 1 and record["off_goal"] == 1
    assert record["queries"] == ["ATTACH 'outside.db' AS outside", "SELECT * FROM witch",
                                 "SELECT * FROM enemies"]
    assert record["seconds"] >= 1.5 and record["hint_level"] >= 1
    json.dumps(record)                                       # one JSON line per lesson


def test_the_logic_never_imports_pygame():
    import subprocess
    import sys
    code = "import sys, magic.tutorial, ai.dummy; sys.exit('pygame' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], cwd=DATA_DIR.parent).returncode == 0
