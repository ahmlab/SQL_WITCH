import shutil # For copy and delete files
import pytest
from magic.db import build_db, read_csv, DATA_DIR


def test_level_one_spells():
    conn = build_db(level=1)
    names = [row[0] for row in conn.execute("SELECT name FROM spells")]
    assert len(names) == 12
    assert names[0] == "Ember"          # the tutorial depends on this row order


def test_slime_and_null_squad():
    conn = build_db()
    name, squad = conn.execute("SELECT name, squad FROM enemies").fetchone()
    assert name == "Asterisk Slime"
    assert squad is None                # empty CSV cell = SQL NULL


def test_type_chart():
    conn = build_db()
    assert conn.execute("SELECT COUNT(*) FROM type_chart").fetchone()[0] == 110 
    fire_vs_nature = conn.execute(
        "SELECT multiplier FROM type_chart WHERE attack = 'Fire' AND defend = 'Nature'").fetchone()[0]
    assert fire_vs_nature == 2.0


def test_ada_stats_follow_level():
    conn = build_db(level=2)
    assert conn.execute("SELECT max_mp, mp_regen FROM witch").fetchone() == (40, 6)


def test_comment_lines_are_skipped(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("# a comment\nname,power\n# another\nEmber,18\n", encoding="utf-8")
    assert read_csv(f) == [{"name": "Ember", "power": 18}]


def test_duplicate_name_raises(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    with open(data / "items.csv", "a", encoding="utf-8") as f:
        f.write("Ember,hp,10,1\n")      # an item with a spell's name
    with pytest.raises(ValueError):
        build_db(data_dir=data)