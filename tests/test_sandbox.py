import time

import pytest

from magic.db import build_db
from magic.guard import Miscast, run_query, sandbox

def test_a_normal_query_returns_columns_and_rows():
    conn = build_db()
    columns, rows = run_query(conn, "SELECT name, mp_cost FROM spells LIMIT 2")
    assert columns == ["name", "mp_cost"]
    assert rows[0] == ("Ember", 3)


@pytest.mark.parametrize("sql", [
    "DELETE FROM spells",
    "UPDATE spells SET power = 999",
    "INSERT INTO spells (name) VALUES ('Cheat')",
    "DROP TABLE spells",
])
def test_the_database_itself_refuses_to_be_rewritten(sql):
    conn = build_db()
    with pytest.raises(Miscast):
        run_query(conn, sql)
    assert conn.execute("SELECT COUNT(*) FROM spells").fetchone()[0] == 12


def test_only_whitelisted_functions_are_allowed():
    conn = build_db()
    run_query(conn, "SELECT COUNT(*) FROM spells")          # allowed
    with pytest.raises(Miscast):
        run_query(conn, "SELECT upper(name) FROM spells")   # not on the list


def test_a_cross_join_bomb_is_cut_off_in_time():
    conn = build_db()
    bomb = ("SELECT COUNT(*) FROM spells a, spells b, spells c, spells d, "
            "spells e, spells f, spells g, spells h, spells i, spells j")
    start = time.perf_counter()
    with pytest.raises(Miscast, match="collapsed"):
        run_query(conn, bomb)
    assert time.perf_counter() - start < 1.0


def test_the_engine_can_still_write_after_a_player_query():
    conn = build_db()
    run_query(conn, "SELECT name FROM spells")
    conn.execute("UPDATE witch SET hp = 42")                # the engine, not the player
    assert conn.execute("SELECT hp FROM witch").fetchone()[0] == 42


def test_the_sandbox_is_removed_even_if_the_query_explodes():
    conn = build_db()
    with pytest.raises(Exception):
        with sandbox(conn):
            conn.execute("SELECT * FROM table_that_does_not_exist")
    conn.execute("UPDATE witch SET mp = 7")
    assert conn.execute("SELECT mp FROM witch").fetchone()[0] == 7