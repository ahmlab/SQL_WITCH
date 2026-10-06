"""I call it guard.py because the work of this baddie is to separate which queries work against does queries that doesn't work  (•◡•) """

import sqlglot # Creates a tree for the queries so we can analize what queries the players are choosing
from sqlglot import exp
from sqlglot.errors import ParseError
import logging

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
    exp.Drop: "Ada: Drop the tables? MY LIVE is in these tables!",
    exp.Delete: "Ada: Yo I don't think we can do that without unbelivable consequences.",
    exp.Update: "Ada: Oh no, I'm new in this world and you too, we are not gonna do that.",
    exp.Insert: "Ada: What are we now? The Dungeon Master. I won't take such approach now",
    exp.Create: "Ada: Create a table? Really? I'm level one in this world, come on!.",
    exp.Alter: "Ada: Mmm... no, I'm not gonna do it.",
    exp.Union: "Ada: I'm not ready for commitment. One SELECT, please.",
    exp.Except: "Ada: EXCEPT what? Except you, trying to break everything. One SELECT, please.",
    exp.Intersect: "Ada: INTERSECT? Our paths have intersected enough already. One SELECT, please.",
    exp.Pragma: "Grimoire: *Angry noises*.",
    exp.Attach: "Ada: ATTACH another database? Absolutely not. We have enough monsters here.",
}
INJECTION = "Ada: Hahaha no. Put the semicolon down and step away from the database of this world.",
GIBBERISH = "Ada: Mmm that was NOT the right way of making the spell.",
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