"""I call it guard.py because the work of this baddie is to separate which queries work against does queries that doesn't work  (•◡•)

Sandbox v2 (plan §4.1, decision D10): the player may write any SQL the world allows. What the
guard still refuses is only what would hurt the *program*, never the *world*:

    refused (program safety)            allowed (world freedom)
    ATTACH, DETACH, VACUUM               SELECT and friends: WITH (RECURSIVE), UNION, EXCEPT, INTERSECT
    load_extension and every function    INSERT, REPLACE, UPDATE, DELETE
      not on the whitelist               CREATE TABLE / VIEW / INDEX / TRIGGER, DROP, ALTER
    PRAGMAs except a few read-only ones  BEGIN, SAVEPOINT, RELEASE, ROLLBACK, COMMIT
    more than one statement per cast,
      except one BEGIN ... COMMIT block
    anything over the time budget, the page limit or the SQLite limits set by harden()

The world's consequences (a dropped table, a deleted foe, a duplicate name) are not the guard's
business: magic/world.py checks the world after every query and reacts.

How a query is read:
1. split() cuts the text into statements with SQLite's own sqlite3.complete_statement, so a
   trigger body full of semicolons stays one statement (sqlglot cannot parse triggers).
2. classify() names each statement by its leading keywords: kind (read, write, schema,
   transaction), verb and target table.
3. Reads are parsed with sqlglot for the technique signature and the forgery ward: a SELECT
   list (or a view's) may not contain string literals, so spell names are read, not typed.
   An INSERT may of course contain literals: that is how the player brings things in.
4. run_query() executes them in order under the authorizer and the time budget. A failure
   inside a transaction block rolls it back; a transaction left open is rolled back too,
   because a snapshot (the Rewind) cannot be taken while one is open.

inspect() returns a Signature: the set of techniques used (it feeds the Codex, the Hint
Director and the player model; it never locks anything) plus the overall kind.

STATUS: sandbox v2 (D10): free world, program-safety limits, signatures with kinds.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass

import sqlglot  # Creates a tree for the queries so we can analyze what queries the players are choosing
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError

from i18n import t

# sqlglot logs a warning for syntax it does not understand; keep the game console clean.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

# print(repr(sqlglot.parse_one("SELECT name FROM spells WHERE power > 10", read="sqlite"))) # Uncomment to see the tree

# Each technique of a read query and the syntax-tree node that proves it was used.
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
    "UNION": exp.Union,
    "EXCEPT": exp.Except,
    "INTERSECT": exp.Intersect,
}
# Techniques of the other statements, by verb (and, for CREATE, by what is created).
VERB_TECHNIQUES = {"insert": "INSERT", "replace": "INSERT", "update": "UPDATE",
                   "delete": "DELETE", "drop": "DROP", "alter": "ALTER", "pragma": "PRAGMA",
                   "begin": "TRANSACTION", "commit": "TRANSACTION", "end": "TRANSACTION",
                   "rollback": "TRANSACTION", "savepoint": "TRANSACTION",
                   "release": "TRANSACTION"}

KINDS = {"select": "read", "with": "read", "values": "read", "explain": "read",
         "pragma": "read", "insert": "write", "replace": "write", "update": "write",
         "delete": "write", "create": "schema", "drop": "schema", "alter": "schema",
         "analyze": "schema", "reindex": "schema", "begin": "transaction",
         "commit": "transaction", "end": "transaction", "rollback": "transaction",
         "savepoint": "transaction", "release": "transaction"}
REFUSED = {"attach": "miscast.attach", "detach": "miscast.detach", "vacuum": "miscast.vacuum"}
SAFE_PRAGMAS = {"table_info", "table_xinfo", "table_list", "index_list", "index_info",
                "index_xinfo", "foreign_key_list"}
OPENERS = {"begin", "savepoint"}
CLOSERS = {"commit", "end", "rollback", "release"}
KIND_ORDER = ("read", "transaction", "write", "schema")   # a block's kind: its strongest part


class Miscast(Exception):
    """A query the magic system refuses. Its text, from the catalog, is shown to the player."""

    def __init__(self, key: str, **args):
        self.key, self.params = key, args
        super().__init__(t(key, **args))


@dataclass(frozen=True)
class Statement:
    """One statement of a cast, as the guard reads it."""
    sql: str
    kind: str                    # read | write | schema | transaction
    verb: str                    # select, insert, drop, begin, ...
    target: str | None = None    # the table (or view, index, trigger) it is about, lowercase
    what: str | None = None      # for create/drop: table | view | index | trigger
    detail: str | None = None    # for alter: "rename table", "rename column", "add", "drop"
    on: str | None = None        # for create index/trigger: the table it is on


class Signature(frozenset):
    """The techniques a cast used (a frozenset of names like "LIMIT") plus what kind of cast
    it was and its statements. Comparing it with a set still works as before."""

    def __new__(cls, techniques=(), kind: str = "read", statements: tuple = ()):
        self = super().__new__(cls, techniques)
        self.kind = kind
        self.statements = statements
        return self


# ------------------------------------------------------------------ reading the text

_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_WORD = re.compile(r'"(?:[^"]|"")*"|`[^`]*`|\[[^\]]*\]|[A-Za-z_][A-Za-z0-9_$]*|\(|\)|\.|;')


def split(sql: str) -> list[str]:
    """Cut a cast into statements the way SQLite would (a trigger body stays whole)."""
    statements, current = [], ""
    for part in re.split(r"(;)", sql):
        current += part
        if part == ";" and sqlite3.complete_statement(current):
            if current.strip(" \t\r\n;"):
                statements.append(current.strip())
            current = ""
    if current.strip(" \t\r\n;"):
        statements.append(current.strip())
    return statements


def _words(sql: str) -> list[str]:
    return _WORD.findall(_COMMENTS.sub(" ", sql))


def _name(token: str | None) -> str | None:
    if token is None:
        return None
    if token[0] in "\"`[":
        token = token[1:-1]
    return token.lower()


def _after(words: list[str], i: int, skip: tuple[str, ...]) -> tuple[str | None, int]:
    """The identifier at position i, skipping keywords like IF NOT EXISTS and a schema prefix."""
    while i < len(words) and words[i].upper() in skip:
        i += 1
    if i >= len(words):
        return None, i
    name = words[i]
    if i + 2 < len(words) and words[i + 1] == ".":          # main.spells -> spells
        name, i = words[i + 2], i + 2
    return _name(name), i + 1


def classify(sql: str) -> Statement:
    """Name a single statement: its kind, verb and target (read from its leading keywords)."""
    words = _words(sql)
    if not words:
        raise Miscast("miscast.empty")
    verb = words[0].lower()
    upper = [w.upper() for w in words]
    if verb in REFUSED:
        raise Miscast(REFUSED[verb])
    if verb not in KINDS:
        raise Miscast("miscast.not_understood")
    kind = KINDS[verb]
    if verb == "with":                       # WITH ... can lead to a SELECT or to a write
        kind, verb = _with_kind(sql)
    target = what = detail = on = None
    if verb in ("insert", "replace"):
        target, _ = _after(words, upper.index("INTO") + 1 if "INTO" in upper else 1, ())
    elif verb == "update":
        target, _ = _after(words, 1, ("OR", "ROLLBACK", "ABORT", "REPLACE", "FAIL", "IGNORE"))
    elif verb == "delete":
        target, _ = _after(words, upper.index("FROM") + 1 if "FROM" in upper else 1, ())
    elif verb in ("create", "drop"):
        i = 1
        while i < len(upper) and upper[i] in ("TEMP", "TEMPORARY", "UNIQUE", "VIRTUAL"):
            i += 1
        what = upper[i].lower() if i < len(upper) else None
        if what == "table" and verb == "create" and "VIRTUAL" in upper[:i]:
            raise Miscast("miscast.denied")
        target, j = _after(words, i + 1, ("IF", "NOT", "EXISTS"))
        if verb == "create" and what in ("index", "trigger") and "ON" in upper[j:]:
            on, _ = _after(words, upper.index("ON", j) + 1, ())
    elif verb == "alter":
        target, j = _after(words, 2, ())
        rest = upper[j:]
        detail = ("rename table" if rest[:2] == ["RENAME", "TO"] else
                  "rename column" if rest[:1] == ["RENAME"] else
                  "add" if rest[:1] == ["ADD"] else "drop" if rest[:1] == ["DROP"] else None)
    elif verb == "pragma":
        name = _name(words[1]) if len(words) > 1 else ""
        if len(words) > 3 and words[2] == ".":
            name = _name(words[3])
        if name not in SAFE_PRAGMAS or "=" in sql:
            raise Miscast("miscast.pragma")
        target = name
    return Statement(sql=sql, kind=kind, verb=verb, target=target, what=what, detail=detail,
                     on=on)


def _with_kind(sql: str) -> tuple[str, str]:
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except (ParseError, TokenError):
        return "read", "with"
    for node, verb in ((exp.Insert, "insert"), (exp.Update, "update"), (exp.Delete, "delete")):
        if isinstance(tree, node):
            return "write", verb
    return "read", "with"


# ------------------------------------------------------------------ techniques and forgery

def parse_read(sql: str):
    """The sqlglot tree of a read statement (SELECT, WITH ... SELECT, UNION ...)."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except (ParseError, TokenError):
        raise Miscast("miscast.gibberish")
    if len(statements) != 1:
        raise Miscast("miscast.one_at_a_time")
    return statements[0]


def parse_one_select(sql: str):
    """Kept for the styles and the tutorial: the tree of a single read query."""
    statement = classify(split(sql)[0] if split(sql) else "")
    if statement.kind != "read" or statement.verb == "pragma":
        raise Miscast("miscast.not_understood")
    return parse_read(sql)


def runes_used(tree) -> set[str]:
    """The techniques that appear anywhere in a read query, subqueries included."""
    return {rune for rune, node in RUNES.items() if tree.find(node) is not None}


def check_forgery(tree) -> None:
    """No string literal may appear in any SELECT list: names must be read from a table."""
    for select in tree.find_all(exp.Select):
        for column in select.expressions:
            for literal in column.find_all(exp.Literal):
                if literal.is_string:
                    raise Miscast("miscast.forgery")


def _techniques(statement: Statement) -> set[str]:
    if statement.kind == "read" and statement.verb not in ("pragma", "explain"):
        tree = parse_read(statement.sql)
        check_forgery(tree)
        return runes_used(tree)
    found = set()
    if statement.verb == "create":
        found.add(f"CREATE {(statement.what or 'table').upper()}")
        if statement.what == "view":                       # a view's SELECT is read later:
            body = re.split(r"\bAS\b", statement.sql, maxsplit=1, flags=re.I)
            if len(body) == 2:                             # forging names into it is still forging
                tree = parse_read(body[1])
                check_forgery(tree)
                found |= runes_used(tree)
    elif statement.verb in VERB_TECHNIQUES:
        found.add(VERB_TECHNIQUES[statement.verb])
    return found


def inspect(sql: str, unlocked=None) -> Signature:
    """Read a cast before it runs. Returns its Signature; raises Miscast for what is refused.
    `unlocked` is ignored: since the Codex replaced the rune gate, no technique is locked."""
    texts = split(sql)
    if not texts:
        raise Miscast("miscast.empty")
    statements = tuple(classify(text) for text in texts)
    if len(statements) > 1:
        # Several statements only as one transaction block: BEGIN ... COMMIT (or ROLLBACK).
        if statements[0].verb not in OPENERS or statements[-1].verb not in CLOSERS:
            raise Miscast("miscast.one_at_a_time")
    techniques: set[str] = set()
    for statement in statements:
        techniques |= _techniques(statement)
    kinds = {s.kind for s in statements}
    kind = max(kinds, key=KIND_ORDER.index)
    if len(statements) > 1:
        kind = "transaction"
    return Signature(techniques, kind, statements)


# ---------------------------------------------------------------- the sandbox--------------------------------------------------------------------#

# SQLite tells the authorizer what a query is about to do. Program safety only.
ALLOWED_ACTIONS = {getattr(sqlite3, name) for name in (
    "SQLITE_SELECT", "SQLITE_READ", "SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE",
    "SQLITE_CREATE_TABLE", "SQLITE_CREATE_TEMP_TABLE", "SQLITE_CREATE_VIEW",
    "SQLITE_CREATE_TEMP_VIEW", "SQLITE_CREATE_INDEX", "SQLITE_CREATE_TEMP_INDEX",
    "SQLITE_CREATE_TRIGGER", "SQLITE_CREATE_TEMP_TRIGGER", "SQLITE_DROP_TABLE",
    "SQLITE_DROP_TEMP_TABLE", "SQLITE_DROP_VIEW", "SQLITE_DROP_TEMP_VIEW", "SQLITE_DROP_INDEX",
    "SQLITE_DROP_TEMP_INDEX", "SQLITE_DROP_TRIGGER", "SQLITE_DROP_TEMP_TRIGGER",
    "SQLITE_ALTER_TABLE", "SQLITE_TRANSACTION", "SQLITE_SAVEPOINT", "SQLITE_RECURSIVE",
    "SQLITE_ANALYZE", "SQLITE_REINDEX")}
ALLOWED_FUNCTIONS = {"count", "sum", "avg", "min", "max", "total", "coalesce", "ifnull",
                     "nullif", "iif", "abs", "round", "length", "lower", "upper", "substr",
                     "substring", "replace", "typeof", "trim", "ltrim", "rtrim", "instr",
                     "group_concat", "like", "glob", "printf", "format"}
# random, randomblob and zeroblob are not allowed: chance comes from the battle's rng only, and
# blobs are a way to fill memory. SQLite's own ALTER TABLE calls functions named sqlite_*.
INTERNAL_PREFIX = "sqlite_"

BUDGET_S = 0.05                  # the time a cast may take, triggers included
MAX_PAGES = 2560                 # 10 MB of 4 KB pages; the battle database uses about 13
LIMITS = {"SQLITE_LIMIT_SQL_LENGTH": 20_000, "SQLITE_LIMIT_COMPOUND_SELECT": 16,
          "SQLITE_LIMIT_EXPR_DEPTH": 200, "SQLITE_LIMIT_TRIGGER_DEPTH": 8,
          "SQLITE_LIMIT_LIKE_PATTERN_LENGTH": 100, "SQLITE_LIMIT_COLUMN": 200,
          "SQLITE_LIMIT_ATTACHED": 0}


def _authorizer(action, arg1, arg2, db_name, trigger):
    """Called by SQLite for every table, column, function and statement a query touches."""
    if action == sqlite3.SQLITE_FUNCTION:          # arg2 holds the function name
        name = (arg2 or "").lower()
        if name in ALLOWED_FUNCTIONS or name.startswith(INTERNAL_PREFIX):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA:
        return sqlite3.SQLITE_OK if (arg1 or "").lower() in SAFE_PRAGMAS else sqlite3.SQLITE_DENY
    if action in ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY                     # ATTACH, DETACH, virtual tables...


def harden(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Prepare a battle database for free players: explicit transactions (no hidden BEGIN from
    Python), a page limit and SQLite's own limits on query size and depth."""
    conn.isolation_level = None
    conn.execute(f"PRAGMA max_page_count = {MAX_PAGES}")
    for name, value in LIMITS.items():
        if hasattr(sqlite3, name):
            conn.setlimit(getattr(sqlite3, name), value)
    return conn


@contextmanager
def sandbox(conn, budget_s: float = BUDGET_S):
    """Watch every action and the clock, then give the engine its full permissions back."""
    deadline = time.perf_counter() + budget_s
    conn.set_authorizer(_authorizer)
    conn.set_progress_handler(lambda: time.perf_counter() > deadline, 10_000)
    try:
        yield conn
    finally:                                       # the engine must be able to write again
        conn.set_authorizer(None)
        conn.set_progress_handler(None, 0)


def _miscast_for(error: sqlite3.Error) -> Miscast:
    text = str(error)
    if "interrupted" in text:
        return Miscast("miscast.too_slow")
    if "full" in text or "too big" in text or "too large" in text:
        return Miscast("miscast.too_big")
    if isinstance(error, sqlite3.IntegrityError):
        return Miscast("miscast.refused_constraint", error=text)
    if "not authorized" in text or "prohibited" in text:
        return Miscast("miscast.denied")
    return Miscast("miscast.not_understood_error", error=text)


@dataclass
class Outcome:
    """What running a cast did, beyond its rows."""
    rolled_back: bool = False        # a transaction was left open and the guard rolled it back
    changes: int = 0                 # rows the cast inserted, updated or deleted
    committed: bool = False          # a transaction block was committed
    note: str | None = None          # "rollback_no_transaction", "commit_no_transaction"


def run_query(conn, sql, max_rows: int = 200, outcome: Outcome | None = None):
    """Run a player or foe cast safely, statement by statement. Returns the (columns, rows) of
    the last statement that produced a result, or ([], []) when none did."""
    texts = split(sql) or [sql]
    outcome = outcome if outcome is not None else Outcome()
    columns, rows = [], []
    before = conn.total_changes
    first = _words(texts[0])[:1]
    if len(texts) == 1 and first and first[0].lower() in ("rollback", "commit", "end") \
            and not conn.in_transaction:
        # Nothing to undo or to commit: not an error of the world, a lesson (a reaction).
        outcome.note = "rollback_no_transaction" if first[0].lower() == "rollback" \
            else "commit_no_transaction"
        return columns, rows
    try:
        with sandbox(conn):                        # fetch inside: SQLite runs lazily
            for text in texts:
                was_open = conn.in_transaction
                cursor = conn.execute(text)
                if cursor.description is not None:
                    columns = [d[0] for d in cursor.description]
                    rows = cursor.fetchmany(max_rows + 1)  # +1 detects a catastrophic overflow
                verb = (_words(text)[:1] or [""])[0].lower()
                if was_open and not conn.in_transaction and verb in ("commit", "end"):
                    outcome.committed = True
    except sqlite3.Error as error:
        if conn.in_transaction:
            conn.execute("ROLLBACK")               # all or nothing
        raise _miscast_for(error)
    finally:
        if conn.in_transaction:                    # left open: a snapshot cannot wait for it
            conn.execute("ROLLBACK")
            outcome.rolled_back = True
    outcome.changes = conn.total_changes - before
    return columns, rows
