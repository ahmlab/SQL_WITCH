"""Player statistics, computed from the save's own log (prompt 05 §3). For the player, not for a
teacher: how they cast, which techniques they use and since when, which tables they read, how
fast their queries run, how their battles went, and their habits (sessions, Fatigue).

Every function takes plain lists of records (GameState.log: one dict per cast, GameState.battles:
one per battle), so a fixture log can be checked by hand. A cast record has: t, run, battle,
guardian, turn, sql, kind, techniques, tables, rows, read, cast, overflow, fizzles, mp_spent,
mp_wasted, ms, scanned, plan, scry, miscast.

The learning metric of the school report is here too: uses of a guardian's technique before its
battle and after it ("you started using WHERE in the Filter Keep and have used it 41 times").

Exports: the log as CSV, and the Scrolls as a .sql file that re-creates them in any SQLite.

Never imports pygame.

STATUS: casting, technique (first use, before/after), tables, queries, battles, habits, exports.
"""

from __future__ import annotations

import csv
import io
from collections import Counter

CSV_FIELDS = ("t", "run", "battle", "guardian", "turn", "kind", "techniques", "tables", "rows",
              "read", "cast", "overflow", "fizzles", "mp_spent", "mp_wasted", "ms", "scanned",
              "scry", "miscast", "sql")


def cast_record(report, sql: str, guardian: str, turn: int, ms: float, plan: list[str],
                scanned: int, tables: set[str] | None = None) -> dict:
    """One line of the persistent log, from a magic.cast.CastReport."""
    import time
    return {
        "t": round(time.time()), "guardian": guardian, "turn": turn, "sql": sql,
        "kind": report.kind, "techniques": sorted(report.runes), "tables": sorted(tables or ()),
        "rows": len(report.rows), "read": min(report.visible, len(report.rows)),
        "cast": len(report.casts), "overflow": report.overflow, "fizzles": len(report.fizzles),
        "mp_spent": report.mp_spent, "mp_wasted": sum(getattr(f, "paid", 0) for f in report.fizzles),
        "ms": round(ms, 3), "scanned": scanned, "plan": plan, "scry": report.scry,
        "miscast": False,
    }


def miscast_record(sql: str, guardian: str, turn: int, key: str) -> dict:
    import time
    return {"t": round(time.time()), "guardian": guardian, "turn": turn, "sql": sql,
            "miscast": True, "reason": key}


def casts_only(log: list[dict]) -> list[dict]:
    return [r for r in log if not r.get("miscast")]


def casting(log: list[dict]) -> dict:
    good = casts_only(log)
    rows = sum(r.get("rows", 0) for r in good)
    read = sum(r.get("read", 0) for r in good)
    trend = [round(r["read"] / r["rows"], 2) if r.get("rows") else 1.0 for r in good[-20:]]
    return {
        "queries": len(good),
        "free_looks": sum(1 for r in good if r.get("scry")),
        "miscasts": sum(1 for r in log if r.get("miscast")),
        "overflows": sum(1 for r in good if r.get("overflow", 0) > 0),
        "fizzles": sum(r.get("fizzles", 0) for r in good),
        "rows_summoned": rows,
        "rows_read": read,
        "mp_spent": sum(r.get("mp_spent", 0) for r in good),
        "mp_wasted": sum(r.get("mp_wasted", 0) for r in good),
        "rows_per_query": round(rows / len(good), 2) if good else 0.0,
        "efficiency_trend": trend,                 # rows read / rows summoned, last 20 casts
    }


def technique(log: list[dict], signatures: dict[str, str] | None = None) -> dict:
    """Uses per technique, the first use of each (when and where), and for each guardian's
    technique the uses before its first battle and after it."""
    counts: Counter[str] = Counter()
    first: dict[str, dict] = {}
    for r in casts_only(log):
        for tech in r.get("techniques", ()):
            counts[tech] += 1
            first.setdefault(tech, {"t": r.get("t"), "guardian": r.get("guardian")})
    learned = {}
    for guardian, tech in (signatures or {}).items():
        if not tech:
            continue
        met = next((i for i, r in enumerate(log) if r.get("guardian") == guardian), None)
        if met is None:
            continue
        before = sum(1 for r in casts_only(log[:met]) if tech in r.get("techniques", ()))
        since = sum(1 for r in casts_only(log[met:]) if tech in r.get("techniques", ()))
        learned[tech] = {"guardian": guardian, "before": before, "since": since}
    return {"counts": dict(counts.most_common()), "first": first, "learned": learned}


def tables(log: list[dict], every_table: set[str] | None = None) -> dict:
    counts: Counter[str] = Counter()
    for r in casts_only(log):
        counts.update(r.get("tables", ()))
    never = sorted(set(every_table or ()) - set(counts))
    return {"counts": dict(counts.most_common()), "never": never}


def queries(log: list[dict]) -> list[dict]:
    """Each query with its real execution time, rows scanned vs returned, and its plan."""
    return [{"sql": r.get("sql", ""), "ms": r.get("ms", 0.0), "scanned": r.get("scanned", 0),
             "returned": r.get("rows", 0), "plan": r.get("plan", []),
             "index": any("USING" in step and "INDEX" in step for step in r.get("plan", []))}
            for r in casts_only(log)]


def battles(records: list[dict]) -> dict:
    retries: Counter[str] = Counter()
    for b in records:
        if b.get("result") != "ada":
            retries[b.get("guardian", "?")] += 1
    return {
        "battles": len(records),
        "won": sum(1 for b in records if b.get("result") == "ada"),
        "seconds": sum(b.get("seconds", 0) for b in records),
        "rounds": sum(b.get("rounds", 0) for b in records),
        "retries": dict(retries),
        "rewinds": sum(b.get("rewinds", 0) for b in records),
        "tricks": sum(b.get("tricks", 0) for b in records),
        "scrolls": sum(b.get("scrolls", 0) for b in records),
        "per_battle": [{k: b.get(k) for k in ("guardian", "result", "rounds", "seconds")}
                       for b in records],
    }


def habits(sessions: list[dict], time_in: dict, records: list[dict]) -> dict:
    return {
        "sessions": len(sessions),
        "seconds": sum(s.get("seconds", 0) for s in sessions),
        "time_in": dict(time_in),
        "fatigue": [b.get("fatigue", 0.0) for b in records],     # after each battle
    }


def summary(state, signatures: dict[str, str] | None = None,
            every_table: set[str] | None = None, run: str | None = None) -> dict:
    """All sections for one profile's save; run= keeps one run only."""
    log = [r for r in state.log if run is None or r.get("run") == run]
    fights = [b for b in state.battles if run is None or b.get("run") == run]
    return {"casting": casting(log), "technique": technique(log, signatures),
            "tables": tables(log, every_table), "queries": queries(log),
            "battles": battles(fights),
            "habits": habits(state.sessions, getattr(state, "time_in", {}), fights)}


def export_csv(log: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for r in log:
        row = dict(r)
        row["techniques"] = " ".join(r.get("techniques", ()))
        row["tables"] = " ".join(r.get("tables", ()))
        writer.writerow(row)
    return out.getvalue()


def export_scrolls_sql(scrolls: dict[str, str]) -> str:
    """The Scrolls as SQL: run it in any SQLite database that has the game's tables."""
    lines = ["-- SQL Witch: your Scrolls. Each one is a view (Codex: CREATE VIEW).", ""]
    for name, sql in scrolls.items():
        lines.append(f'CREATE VIEW IF NOT EXISTS "scroll_{name}" AS {sql.strip().rstrip(";")};')
    return "\n".join(lines) + "\n"
