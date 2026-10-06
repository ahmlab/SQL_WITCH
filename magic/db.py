import csv
import sqlite3
from pathlib import Path

# Directory of csv files
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SCHEMA = """
CREATE TABLE witch      (name TEXT PRIMARY KEY, hp INT, max_hp INT, mp INT, max_mp INT,
                         mp_regen INT, speed INT, element TEXT, ward INT);
CREATE TABLE spells     (id INTEGER PRIMARY KEY, name TEXT, element TEXT, power INT,
                         mp_cost INT, kind TEXT, unlock_level INT);
CREATE TABLE items      (name TEXT PRIMARY KEY, kind TEXT, amount INT, qty INT);
CREATE TABLE enemies    (id INTEGER PRIMARY KEY, name TEXT, hp INT, max_hp INT, mp INT,
                         max_mp INT, element TEXT, weakness TEXT, speed INT, squad TEXT);
CREATE TABLE foe_spells (foe_id INT REFERENCES enemies(id), name TEXT, element TEXT,
                         power INT, mp_cost INT, kind TEXT);
CREATE TABLE type_chart (attack TEXT, defend TEXT, multiplier REAL, PRIMARY KEY (attack, defend));
CREATE TABLE relics     (name TEXT PRIMARY KEY, soul INT);
CREATE TABLE query_log  (turn INT, caster TEXT, sql TEXT, clauses TEXT,
                         rows_out INT, rows_cast INT, seed INT);
"""

def convert(value):
    """Turns csv values into Python values"""
    if value == "":
        return None # None is NULL for SQL
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value # If its not empty and not a number then its a word ¯\_(ツ)_/¯

def read_csv(path):
    """Read a CSV file into a list of dicts, skipping comment lines that start with '#'."""
    with open(path, newline="", encoding="utf-8") as f:
        lines = (line for line in f if not line.lstrip().startswith("#"))
        rows = []                                  
        for row in csv.DictReader(lines):          # each line comes as a text dictionary
            converted = {}                         # we save here the line
            for key, value in row.items():         # column and value
                converted[key] = convert(value)    
            rows.append(converted)                 
        return rows                                # final list

def check_unique_names(tables):
    """Every name must be unique across all files, or the casting contract cannot tell them apart. (∩ ͡° ͜ʖ ͡°)⊃━☆ﾟ. *"""
    seen = {}
    for table_name, rows in tables.items():
        for row in rows:
            name = row["name"]
            if name in seen:
                raise ValueError(f"Name '{name}' appears in both {seen[name]} and {table_name}")
            seen[name] = table_name

def insert_rows(conn, table, rows):
    """Insert a list of dicts into a table. Column names come from our own CSV headers."""
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    conn.executemany(sql, [tuple(row[c] for c in columns) for row in rows])

def build_db(level=1, data_dir=DATA_DIR):
    """Create a fresh in-memory battle database for Ada at the given level."""
    data_dir = Path(data_dir)
    spells = read_csv(data_dir / "spells.csv")
    items = read_csv(data_dir / "items.csv")
    foes = read_csv(data_dir / "foes.csv")
    foe_spells = read_csv(data_dir / "foe_spells.csv")
    witch = read_csv(data_dir / "witch.csv")
    levels = {row["level"]: row for row in read_csv(data_dir / "levels.csv")}
    type_chart = read_csv(data_dir / "type_chart.csv")

    # Check the whole catalogue, including spells Ada has not unlocked yet.
    check_unique_names({"spells.csv": spells, "items.csv": items, "foes.csv": foes,
                        "foe_spells.csv": foe_spells, "witch.csv": witch})

    # Ada's stats come from witch.csv, overridden by her current level.
    stats = levels[level]
    ada = dict(witch[0])
    ada.update(hp=stats["max_hp"], max_hp=stats["max_hp"], mp=stats["max_mp"],
               max_mp=stats["max_mp"], mp_regen=stats["mp_regen"])

    # Only the spells Ada knows at this level enter the battle, in CSV order.
    known = [row for row in spells if row["unlock_level"] <= level]

    conn = sqlite3.connect(":memory:") # It means the data is living in the ram, so every battle starts clean
    conn.executescript(SCHEMA)
    insert_rows(conn, "witch", [ada])
    insert_rows(conn, "spells", known)
    insert_rows(conn, "items", items)
    insert_rows(conn, "enemies", foes)
    insert_rows(conn, "foe_spells", foe_spells)
    insert_rows(conn, "type_chart", type_chart)
    conn.commit()
    return conn