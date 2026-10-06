"""I call it guard.py because the work of this baddie is to separate which queries work against does queries that doesn't work  (•◡•) """

import sqlglot # Creates a tree for the queries so we can analize what queries the players are choosing
import logging
import sqlite3
import time

from contextlib import contextmanager
from sqlglot import exp
from sqlglot.errors import ParseError

# print(repr(sqlglot.parse_one("SELECT name FROM spells WHERE power > 10", read="sqlite"))) # Uncomment to see the tree

# Each rune (SQL keyword family) and the syntax-tree node that proves it was used.
RUNES = {
    "WHERE": exp.Where,
    "ORDER BY": exp.Order,
    "LIMIT": exp.Limit,
    "JOIN": exp.Join,
    "GROUP BY": exp.Group,
    "HAVING": exp.Having,
    "DISTINCT": exp.Distinct,
    "SUBQUERY": exp.Subquery,
    "WITH": exp.CTE,
    "IS NULL": exp.Is,
    "COALESCE": exp.Coalesce,
}

# ERROR Check witches, here we guide the player to understand their own mistakes
# We must invest some time to stop the players to try to destroy the databases

class Miscast(Exception):
    """A query the magic system refuses. The message is shown to the player."""

# sqlglot logs a warning for syntax it does not understand; keep the game console clean.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

# Statements that try to change the world instead of reading it, and what the game says back.
# This is the funny layer only: the sandbox (tomorrow) is what actually blocks writes.
FORBIDDEN = {
    exp.Drop: "Ada: Drop the tables? MY LIFE is in these tables!",
    exp.Delete: "Ada: Yo I don't think we can DELETE that without unimaginable consequences.",
    exp.Update: "Ada: Oh no, I'm new in this world and you too, we are not gonna do that.",
    exp.Insert: "Ada: What are we now? The Dungeon Master? I won't take such approach now",
    exp.Create: "Ada: Create a table? Really? I'm level one in this world, come on!.",
    exp.Alter: "Ada: Mmm... no, I'm not gonna ALTER anything.",
    exp.Union: "Ada: I'm not ready for commitment. One SELECT, please.",
    exp.Except: "Ada: EXCEPT what? Except you, trying to break everything. One SELECT, please.",
    exp.Intersect: "Ada: INTERSECT? Our paths have intersected enough already. One SELECT, please.",
    exp.Pragma: "Grimoire: *Angry noises*.",
    exp.Attach: "Ada: ATTACH another database? Absolutely not. We have enough monsters here.",
}
INJECTION = "Ada: Hahaha no. Put the semicolon down and step away from the database of this world."
GIBBERISH = "Ada: Mmm that was NOT the right way of making the spell."
NOT_A_SELECT = "Ada: That's not a SELECT. The grimoire looked at it, sighed, and closed itself."

def forbidden_message(statement):
    """Return the joke for a world-changing statement, or None if it is not one."""
    for node_type, message in FORBIDDEN.items():
        if isinstance(statement, node_type):
            return message
    return None


def parse_one_select(sql):
    """Parse the text and make sure it is exactly one SELECT statement."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except ParseError:
        raise Miscast(GIBBERISH)
    jokes = [forbidden_message(s) for s in statements if forbidden_message(s)]
    if len(statements) > 1 and jokes:
        raise Miscast(INJECTION)            # the classic "SELECT ...; DROP TABLE ..." trick
    if jokes:
        raise Miscast(jokes[0])
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise Miscast(NOT_A_SELECT)
    return statements[0]

def runes_used(tree):
    """Return the set of runes that appear anywhere in the query, subqueries included."""
    used = set()
    for rune, node_type in RUNES.items():
        if tree.find(node_type) is not None:
            used.add(rune)
    return used


def check_forgery(tree):
    """No string literal may appear in any SELECT list: names must be read from a table."""
    for select in tree.find_all(exp.Select):
        for column in select.expressions:
            for literal in column.find_all(exp.Literal):
                if literal.is_string:
                    raise Miscast("Ada: Ink cannot conjure names. Pick them from a table.")


def inspect(sql, unlocked):
    """Validate a query before it runs. Returns its technique signature (the runes used)."""
    tree = parse_one_select(sql)
    used = runes_used(tree)
    locked = used - set(unlocked)
    if locked:
        raise Miscast("Ada: I cannot read these runes yet: " + ", ".join(sorted(locked)))
    check_forgery(tree)
    return used

# ---------------------------------------------------------------- the sandbox--------------------------------------------------------------------#

# SQLite tells the authorizer what a query is about to do. We allow only reads.
ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
ALLOWED_FUNCTIONS = {"count", "sum", "avg", "min", "max", "coalesce", "ifnull", "abs", "round"}

TOO_SLOW = "Ada: That spell collapsed under its own weight. The grimoire is still smoking."
DENIED = "The world refused to listen. Spells read the world, they do not rewrite it."


def _authorizer(action, arg1, arg2, db_name, trigger):
    """Called by SQLite for every table, column and function a query touches."""
    if action == sqlite3.SQLITE_FUNCTION:          # arg2 holds the function name
        if arg2 is not None and arg2.lower() in ALLOWED_FUNCTIONS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action in ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY

@contextmanager
def sandbox(conn, budget_s=0.05):
    """Make the connection read-only and time-limited, then give the permissions back."""
    deadline = time.perf_counter() + budget_s
    conn.set_authorizer(_authorizer)
    conn.set_progress_handler(lambda: time.perf_counter() > deadline, 10_000)
    try:
        yield conn
    finally:                                       # the engine must be able to write again
        conn.set_authorizer(None)
        conn.set_progress_handler(None, 0)

def run_query(conn, sql, max_rows=200):
    """Run a player or foe query safely. Returns (column names, rows)."""
    try:
        with sandbox(conn):                        # fetch inside: SQLite runs lazily
            cursor = conn.execute(sql)
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchmany(max_rows + 1)  # +1 detects a catastrophic overflow
    except sqlite3.OperationalError as error:
        if "interrupted" in str(error):
            raise Miscast(TOO_SLOW)
        raise Miscast(f"Ada: The world does not understand that. ({error})")
    except sqlite3.DatabaseError:
        raise Miscast(DENIED)
    return columns, rows