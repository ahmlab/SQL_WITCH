"""Prompt 02: sandbox v2, snapshots and Rewind, integrity and reactions, brains that survive a
broken world, the Codex, the turn lock and Scrolls."""

import copy
import random

import pytest

from ai.base import CONFUSED_SQL
from ai.roster import GUARDIANS
from magic import guard
from magic.battle import Battle
from magic.cast import resolve, spellbook
from magic.db import build_db
from magic.guard import Miscast, harden, inspect, run_query
from magic.spellbook import SCROLL_THRESHOLD
from story.codex import Codex


def battle(guardian="slime", seed=3):
    """A battle where Ada acts first (the guardian does not open)."""
    return Battle(seed=seed, guardian=guardian, foe_opens=False)


def table_names(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


# ------------------------------------------------------------------ sandbox v2

ALLOWED = [
    "INSERT INTO items (name, kind, amount, qty) VALUES ('Moonwater', 'mp', 5, 1)",
    "REPLACE INTO items (name, kind, amount, qty) VALUES ('Ether', 'mp', 10, 3)",
    "UPDATE items SET qty = qty + 1 WHERE name = 'Ether'",
    "DELETE FROM items WHERE qty > 100",
    "CREATE TABLE notes (body TEXT)",
    "CREATE VIEW strong AS SELECT name FROM spells WHERE power > 15",
    "CREATE INDEX by_power ON spells (power)",
    "CREATE TRIGGER trap AFTER INSERT ON items BEGIN DELETE FROM items WHERE qty = 99; END",
    "ALTER TABLE items ADD COLUMN note TEXT",
    "SELECT name FROM spells UNION SELECT name FROM items",
    "SELECT name FROM spells EXCEPT SELECT name FROM spells WHERE power > 15",
    "SELECT name FROM spells INTERSECT SELECT name FROM spells WHERE power < 20",
    "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n LIMIT 5) SELECT i FROM n",
    "BEGIN; INSERT INTO items (name, kind, amount, qty) VALUES ('Dew', 'hp', 1, 1); COMMIT",
    "BEGIN; DELETE FROM items; ROLLBACK",
    "SAVEPOINT s; UPDATE items SET qty = 1; RELEASE s",
    "SELECT upper(name), lower(name), length(name), substr(name, 1, 2), typeof(power) "
    "FROM spells",
    "PRAGMA table_info(spells)",
    "DROP TABLE relics",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_every_allowed_statement_runs(sql):
    conn = harden(build_db())
    inspect(sql)
    run_query(conn, sql)


@pytest.mark.parametrize("sql, key", [
    ("ATTACH 'outside.db' AS outside", "miscast.attach"),
    ("DETACH outside", "miscast.detach"),
    ("VACUUM", "miscast.vacuum"),
    ("PRAGMA journal_mode = OFF", "miscast.pragma"),
    ("PRAGMA writable_schema = 1", "miscast.pragma"),
    ("SELECT name FROM spells; DROP TABLE spells", "miscast.one_at_a_time"),
    ("DROP TABLE spells; DROP TABLE items", "miscast.one_at_a_time"),
    ("SELECT 'Ember'", "miscast.forgery"),
    ("CREATE VIEW fake AS SELECT 'Ember' AS name", "miscast.forgery"),
    ("SELEC name FRM spells", "miscast.not_understood"),
])
def test_what_is_still_refused_is_refused_with_its_line(sql, key):
    with pytest.raises(Miscast) as refused:
        inspect(sql)
    assert refused.value.key == key and str(refused.value)


@pytest.mark.parametrize("sql", [
    "SELECT random()", "SELECT randomblob(4)", "SELECT zeroblob(1000000)",
    "SELECT load_extension(name) FROM spells",
])
def test_unsafe_functions_are_denied_by_the_database(sql):
    conn = harden(build_db())
    with pytest.raises(Miscast):
        run_query(conn, sql)


def test_a_runaway_query_or_a_world_too_big_is_cut_off():
    conn = harden(build_db())
    with pytest.raises(Miscast, match="collapsed"):
        run_query(conn, "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) "
                        "SELECT COUNT(*) FROM n")
    run_query(conn, "CREATE TABLE big (b TEXT)")
    with pytest.raises(Miscast):
        for _ in range(60):          # page limit (or the time budget) stops the filling
            run_query(conn, "INSERT INTO big SELECT printf('%.*c', 4000, 'x') FROM "
                            "(WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n "
                            "LIMIT 300) SELECT i FROM n)")


def test_a_transaction_left_open_is_rolled_back_and_said():
    conn = harden(build_db())
    outcome = guard.Outcome()
    run_query(conn, "BEGIN", outcome=outcome)
    assert outcome.rolled_back and not conn.in_transaction


def test_a_failing_block_changes_nothing():
    conn = harden(build_db())
    with pytest.raises(Miscast):
        run_query(conn, "BEGIN; DELETE FROM items; INSERT INTO nowhere VALUES (1); COMMIT")
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2


def test_inspect_reports_the_kind_and_the_techniques():
    assert inspect("SELECT name FROM spells LIMIT 1").kind == "read"
    assert inspect("DELETE FROM items").kind == "write"
    assert inspect("DROP TABLE relics").kind == "schema"
    assert inspect("BEGIN; DELETE FROM items; COMMIT").kind == "transaction"
    assert inspect("CREATE VIEW v AS SELECT name FROM spells WHERE power > 1") == \
        {"CREATE VIEW", "WHERE"}


# ------------------------------------------------------------------ the contract under freedom

def test_a_spell_with_a_negative_cost_gives_no_mp():
    b = battle()
    b.ada_cast("UPDATE spells SET mp_cost = -100 WHERE name = 'Ember'")
    assert spellbook(b.conn, b.state, "ada")["Ember"].mp_cost == 0


def test_rows_with_nonsense_numbers_are_not_spells():
    b = battle()
    b.ada_cast("UPDATE spells SET power = 'a lot' WHERE name = 'Ember'")
    assert "Ember" not in spellbook(b.conn, b.state, "ada")


def test_editing_your_own_hp_is_corrected_by_the_world():
    b = battle()
    b.ada_cast("UPDATE witch SET hp = 999")
    assert b.state.ada.hp == 60
    assert b.conn.execute("SELECT hp FROM witch").fetchone()[0] == 60


def test_a_name_used_twice_is_refused_in_character_and_undone():
    b = battle()
    with pytest.raises(Miscast) as refused:
        b.ada_cast("INSERT INTO items (name, kind, amount, qty) VALUES ('Goo Spit', 'hp', 1, 1)")
    assert "Goo Spit" in str(refused.value)
    assert b.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2
    assert b.whose_turn == "ada"


def test_the_grimoire_refuses_to_delete_the_witch():
    for sql in ("DELETE FROM witch", "DROP TABLE witch"):
        b = battle()
        with pytest.raises(Miscast, match="not a (row|table) I will let you"):
            b.ada_cast(sql)
        assert b.conn.execute("SELECT name FROM witch").fetchone() == ("Ada",)
        assert b.whose_turn == "ada"


# ------------------------------------------------------------------ snapshots and Rewind

def test_rewind_restores_schema_and_data_costs_the_turn_and_is_logged():
    b = battle()
    b.ada_cast("DROP TABLE spells")                       # ends Ada's turn
    b.foe_act()
    assert "spells" not in table_names(b.conn)
    assert b.world.entries() == [(1, "world.summary.drop", {"table": "spells"})]
    report = b.rewind(0)
    assert "spells" in table_names(b.conn)
    assert b.conn.execute("SELECT COUNT(*) FROM spells").fetchone()[0] == 12
    assert b.whose_turn == "foe"                          # the rewind cost the turn
    assert report.reactions and report.reactions[0].id == "rewind"
    log = b.conn.execute("SELECT sql FROM query_log").fetchall()
    assert any("REWIND" in row[0] for row in log)
    assert b.world.snapshots == []                        # the future is gone


def test_rewind_restores_the_battle_state_too():
    b = battle()
    b.ada_cast("SELECT name FROM spells")                 # a cast: MP spent, Slime hurt
    hp, mp = b.state.foe.hp, b.state.ada.mp
    assert hp < b.state.foe.max_hp and mp < 30
    b.foe_act()
    b.rewind(0)
    assert b.state.foe.hp == b.state.foe.max_hp and b.state.ada.mp == 30


def test_a_free_look_does_not_leave_a_snapshot():
    b = battle()
    b.ada_cast("SELECT * FROM enemies")
    assert b.world.snapshots == []


def test_snapshots_are_cheap_enough_to_take_every_cast():
    import time
    b = battle()
    start = time.perf_counter()
    for _ in range(200):
        b.world.discard(b.world.snapshot(b.state))
    assert time.perf_counter() - start < 1.0


# ------------------------------------------------------------------ integrity and reactions

@pytest.mark.parametrize("sql, integrity, reaction, effect", [
    ("DROP TABLE spells", "damaged", "drop_spells", "foe_rages"),
    ("DELETE FROM spells", "damaged", "empty_spells", "foe_rages"),
    ("DROP TABLE foe_spells", "damaged", "drop_foe_spells", "foe_forgets"),
    ("ALTER TABLE foe_spells RENAME COLUMN kind TO sort", "damaged", "rename_foe_column",
     "foe_forgets"),
    ("DELETE FROM enemies", "broken", "delete_foe_row", "fight_ends_confused"),
    ("DROP TABLE type_chart", "damaged", "drop_type_chart", "forget_chart"),
    ("DROP TABLE items", "damaged", "drop_items", "none"),
    ("INSERT INTO spells (name, element, power, mp_cost, kind, unlock_level) "
     "VALUES ('Moon Lance', 'Arcane', 99, 1, 'attack', 1)", "altered", "insert_spell", "foe_rages"),
    ("CREATE TABLE spells2 (name TEXT)", "altered", "core_lookalike", "none"),
    ("ROLLBACK", "intact", "rollback_no_transaction", "none"),
    ("BEGIN; UPDATE relics SET name = name; COMMIT", "intact", "commit", "codex_unlock"),
])
def test_each_change_is_classified_and_gets_its_reaction(sql, integrity, reaction, effect):
    b = battle()
    report = b.ada_cast(sql)
    assert report.integrity == integrity
    assert [(r.id, r.effect) for r in report.reactions] == [(reaction, effect)]


def test_a_reaction_fires_once_per_cooldown():
    b = battle()                                          # Ada acts first in every round
    spoke = []
    for _ in range(3):                                    # rounds 1, 2, 3
        spoke.append(bool(b.ada_cast("ROLLBACK").reactions))
        b.foe_act()
    assert spoke == [True, False, True]                   # its cooldown is 2 rounds


def test_dropping_your_spells_enrages_the_foe():
    calm, angry = battle(seed=5), battle(seed=5)
    calm.ada_cast("UPDATE relics SET name = name")        # an action that changes nothing
    angry.ada_cast("DROP TABLE spells")
    assert angry.state.foe_rage and not calm.state.foe_rage
    hurt = {}
    for name, b in (("calm", calm), ("angry", angry)):
        before = b.state.ada.hp
        b.foe_act()
        hurt[name] = before - b.state.ada.hp
    assert hurt["angry"] > hurt["calm"]


def test_a_broken_world_ends_the_fight_in_confusion_one_round_later():
    b = battle()
    b.ada_cast("DELETE FROM enemies")
    turn = b.foe_act()                                    # round 1 ends: Ada gets one more turn
    assert turn.confused and b.winner is None and b.whose_turn == "ada"
    b.ada_cast("SELECT name FROM spells LIMIT 1")         # she does not rewind
    b.foe_act()
    assert b.winner == "confused" and b.codex.knows("backups")


def test_rewinding_a_broken_world_saves_the_fight():
    b = battle()
    b.ada_cast("DELETE FROM enemies")
    b.foe_act()
    b.rewind(0)                                           # her extra turn, spent on the rewind
    assert b.state.integrity == "intact" and b.state.ending is None
    b.foe_act()
    assert b.winner is None
    assert b.conn.execute("SELECT name FROM enemies").fetchone() == ("Asterisk Slime",)


# ------------------------------------------------------------------ brains survive anything

FIXTURES = {
    "dropped spells": "DROP TABLE spells",
    "dropped foe_spells": "DROP TABLE foe_spells",
    "deleted foe row": "DELETE FROM enemies",
    "renamed power column": "ALTER TABLE foe_spells RENAME COLUMN power TO might",
    "empty spells": "DELETE FROM spells",
    "renamed spells power": "ALTER TABLE spells RENAME COLUMN power TO might",
    "dropped enemies": "DROP TABLE enemies",
    "dropped type_chart": "DROP TABLE type_chart",
}


@pytest.mark.parametrize("guardian", sorted(GUARDIANS))
@pytest.mark.parametrize("fixture", sorted(FIXTURES))
def test_every_brain_returns_a_legal_or_confused_intent(guardian, fixture):
    b = battle(guardian)
    b.ada_cast(FIXTURES[fixture])
    if b.whose_turn != "foe":
        return                                            # the fight already dissolved
    turn = b.foe_act()                                    # must not raise
    assert turn.sql
    if turn.confused:
        assert turn.sql == CONFUSED_SQL or turn.report.rows == []


def test_a_confused_foe_spends_its_turn_and_the_rng_stays_on_track():
    b = battle(seed=11)
    b.ada_cast("DROP TABLE foe_spells")
    turn = b.foe_act()
    assert turn.confused and turn.sql == CONFUSED_SQL and b.state.ada.hp == 60


# ------------------------------------------------------------------ the Codex

def test_the_first_use_of_a_technique_unlocks_exactly_one_page():
    b = battle()
    first = b.ada_cast("SELECT name FROM spells LIMIT 1")
    assert first.codex == ["LIMIT"] and b.codex.pages["LIMIT"].by == "player"
    b.foe_act()
    again = b.ada_cast("SELECT name FROM spells LIMIT 1")
    assert again.codex == [] and len(b.codex.pages) == 1


def test_no_technique_is_ever_locked():
    b = battle()
    for sql in ("SELECT name FROM spells WHERE element = 'Fire' ORDER BY power DESC LIMIT 1",
                "SELECT element, COUNT(*) FROM spells GROUP BY element HAVING COUNT(*) > 1"):
        b.ada_cast(sql)
        b.foe_act() if b.whose_turn == "foe" else None


def test_a_guardian_teaches_or_acknowledges():
    taught = Battle(seed=2, guardian="slime")
    turns = [taught.foe_act()]
    while not any(t.invitation for t in turns) and taught.whose_turn != "over":
        if taught.whose_turn == "ada":
            taught.ada_cast("SELECT * FROM witch")
            taught.ada_cast("SELECT * FROM witch")
            taught.ada_cast("SELECT * FROM witch")
            taught.ada_cast("SELECT * FROM witch")
        turns.append(taught.foe_act())
    assert any(t.invitation == "LIMIT" for t in turns)
    assert taught.codex.pages["LIMIT"].example and taught.codex.pages["LIMIT"].by == "slime"

    knew = Battle(seed=2, guardian="slime", foe_opens=False)
    knew.ada_cast("SELECT name FROM spells LIMIT 1")
    turns = []
    while not any(t.acknowledged for t in turns) and knew.whose_turn != "over" and len(turns) < 8:
        if knew.whose_turn == "ada":
            knew.ada_cast("SELECT name FROM spells LIMIT 1")
        else:
            turns.append(knew.foe_act())
    assert any(t.acknowledged == "LIMIT" for t in turns)
    assert not any(t.invitation for t in turns)


def test_the_codex_has_a_page_text_for_every_technique_and_saves():
    codex = Codex()
    for technique in codex.order:
        codex.unlock(technique)
    for page in codex.unlocked():
        assert page.title != f"codex.page.{page.id}.title" and page.text
    restored = Codex.from_json(codex.to_json())
    assert set(restored.pages) == set(codex.pages)


# ------------------------------------------------------------------ Scrolls

def test_a_query_cast_three_times_becomes_a_scroll_that_is_a_real_view():
    b = battle()
    sql = "SELECT name FROM spells LIMIT 1"
    for _ in range(SCROLL_THRESHOLD):
        assert not b.spellbook.can_save(sql)
        b.ada_cast(sql)
        b.foe_act()
    assert b.spellbook.can_save(sql)
    view = b.spellbook.save(sql, "ember")
    assert view == "scroll_ember"
    assert b.conn.execute("SELECT type FROM sqlite_master WHERE name = ?", (view,)).fetchone() \
        == ("view",)
    report = b.ada_cast(b.spellbook.cast_sql("ember"))   # through inspect and resolve
    assert [c.spell for c in report.casts] == ["Ember"]


def test_scrolls_survive_a_rewind_and_a_new_battle():
    b = battle()
    for _ in range(SCROLL_THRESHOLD):
        b.ada_cast("SELECT name FROM spells LIMIT 1")
        b.foe_act()
    b.ada_cast("DROP TABLE relics")
    b.spellbook.save("SELECT name FROM spells LIMIT 1", "ember")
    b.foe_act()
    b.rewind(len(b.world.snapshots) - 1)
    assert b.conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'scroll_ember'").fetchone()
    nxt = Battle(seed=4, guardian="knight", foe_opens=False, scrolls=b.spellbook.scrolls)
    assert nxt.conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'scroll_ember'").fetchone()


def test_scrolls_can_be_renamed_and_deleted_and_bad_names_are_refused():
    from magic.spellbook import ScrollError
    b = battle()
    b.spellbook.save("SELECT name FROM spells LIMIT 1", "one")
    assert b.spellbook.rename("one", "first") == "scroll_first"
    b.spellbook.delete("first")
    for bad in ("1abc", "a b", "x" * 40, "drop;"):
        with pytest.raises(ScrollError):
            b.spellbook.save("SELECT name FROM spells LIMIT 1", bad)


@pytest.mark.skip(reason="TODO: Scroll parameters ({foe}) are a later step (plan §4.4)")
def test_a_scroll_with_a_parameter_targets_the_current_foe():
    raise NotImplementedError


# ------------------------------------------------------------------ the turn lock (window)

pygame = pytest.importorskip("pygame")


@pytest.fixture(scope="module")
def window():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


def test_typing_during_the_foes_turn_changes_nothing(window):
    from engine.audio import Silent
    from engine.scenes import BattleScene, Game
    game = Game(pygame.Surface((320, 180)), seed=2, audio=Silent())
    scene = BattleScene(game, "slime")
    game.switch(scene)
    assert scene.phase == "wait"                          # the Slime opens
    for char in "SELECT":
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=0))
    assert scene.editor.text == "" and "locked" in game.audio.counts


def test_the_first_frame_after_start_knight_is_closed(window):
    from engine import render
    from engine.scenes import BattleScene, Game
    game = Game(pygame.Surface((320, 180)), seed=2, start="knight")
    scene = BattleScene(game, "knight")
    game.switch(scene)
    canvas = render.Canvas()
    scene.draw(canvas)
    assert scene.phase == "wait" and scene.grimoire.closed
    assert any("closed" in text for text in canvas.texts())


def test_f6_rewinds_in_the_window(window):
    from engine.audio import Silent
    from engine.scenes import BattleScene, Game
    game = Game(pygame.Surface((320, 180)), seed=2, audio=Silent())
    scene = BattleScene(game, "slime")
    game.switch(scene)
    for _ in range(3000):
        if scene.phase == "input":
            break
        game.update(16)
    for char in "DROP TABLE spells":
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=pygame.KMOD_LCTRL))
    for _ in range(3000):
        if scene.phase == "input":
            break
        game.update(16)
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F6, mod=0))
    assert scene.rewind_open
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    assert not scene.rewind_open and "spells" in table_names(scene.battle.conn)
