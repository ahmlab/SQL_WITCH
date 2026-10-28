"""Play the Asterisk Slime battle in the terminal: python -m sim.play_cli --seed 7

This is the build that proves the game is fun before any pixel is drawn (design doc 8.1).
It uses exactly the same Battle as the window, and never imports pygame.

STATUS: step 4 done - full battle in the terminal, page cut, MP drain, damage, Invitation.
"""

from __future__ import annotations

import argparse
import time
from typing import Callable

from magic.battle import Battle, FoeTurn
from magic.cast import PAGE_ROWS, CastReport, cell_text, column_widths, effect_word
from magic.guard import Miscast

Out = Callable[[str], None]

INTRO = """\
Ada wakes up on wet grass. Above her, the sky is a table with too many columns.
Something round and green wobbles out of the bushes: the ASTERISK SLIME.

  Type a SQL query and press Enter. Every query is real SQLite.
  A query that returns no spell names is a free look (3 per turn).
  The page holds only {rows} rows: you pay for every spell you summon,
  but only the rows you can read take effect.

  Try:  SELECT * FROM enemies      then   SELECT name FROM spells
  Commands:  :help  :why  :schema  :quit
"""

HELP = """\
  Tables: witch, spells, items, enemies, foe_spells, type_chart, query_log
  A row casts a spell if one of its cells is the name of a spell Ada knows.
  A row uses an item if a cell is an item's name. A combatant's name in the row is the target.
  :why     what the Slime's brain was thinking (the debug overlay)
  :schema  the columns of every table
  :quit    leave the battle"""


# ------------------------------------------------------------------ printing

def bar(value: int, maximum: int, width: int = 10) -> str:
    filled = round(width * value / maximum) if maximum else 0
    return "#" * filled + "." * (width - filled)


def status(battle: Battle) -> list[str]:
    ada, foe = battle.state.ada, battle.state.foe
    runes = ", ".join(sorted(ada.runes)) or "none yet"
    tired = lambda c: "  EXHAUSTED" if c.exhausted else ""
    return [
        f"  {foe.name:<15} HP {foe.hp:>3}/{foe.max_hp:<3} [{bar(foe.hp, foe.max_hp)}]"
        f"  MP {foe.mp:>2}/{foe.max_mp}{tired(foe)}",
        f"  {ada.name:<15} HP {ada.hp:>3}/{ada.max_hp:<3} [{bar(ada.hp, ada.max_hp)}]"
        f"  MP {ada.mp:>2}/{ada.max_mp}  ward {ada.ward}{tired(ada)}",
        f"  Ada's runes: {runes}",
    ]


def page_lines(report: CastReport) -> list[str]:
    """The Grimoire's right page as text, cut at PAGE_ROWS rows and at the page width."""
    if not report.rows:
        return ["  (the page stays blank: no rows)"]
    widths = column_widths(report.columns, report.rows)
    shown = report.visible_columns
    clipped = [report.columns[i] for i in range(len(report.columns)) if i not in shown]
    cast_rows = {c.row for c in report.casts}
    edge = " |>" if clipped else ""

    def line(cells, mark="  "):
        return "  " + mark + " ".join(cells[i].ljust(widths[i]) for i in shown) + edge

    lines = [line(report.columns), "  " + "  " + "-" * max(1, sum(widths[i] + 1 for i in shown))]
    for index, row in enumerate(report.rows[:PAGE_ROWS]):
        lines.append(line([cell_text(v) for v in row], "* " if index in cast_rows else "  "))
    hidden = len(report.rows) - PAGE_ROWS
    if hidden > 0:
        lines.append(f"  --- the page ends here: {hidden} rows kept writing themselves "
                     f"into the margin ---")
    if clipped:
        lines.append(f"  --- cut off at the right edge: {', '.join(clipped)} ---")
    return lines


def narrate(report: CastReport) -> list[str]:
    """Turn the report's events into sentences, in the order they happened."""
    lines, margin = [], []
    for event in report.events:
        kind = event[0]
        if kind == "cast":
            _, _, caster, spell, target, dmg, crit, mult = event
            extra = (" CRITICAL!" if crit else "") + (
                f" ({effect_word(mult)})" if effect_word(mult) else "")
            lines.append(f"  {caster} casts {spell} at {target}: {dmg} damage.{extra}")
        elif kind == "heal":
            lines.append(f"  {event[2]} heals {event[3]} for {event[4]} HP.")
        elif kind == "ward":
            lines.append(f"  {event[2]} raises a ward of {event[4]} on {event[3]}.")
        elif kind == "item":
            what = "MP" if event[4] == "mp" else "HP"
            lines.append(f"  {event[3]} uses {event[2]}: +{event[5]} {what}.")
        elif kind == "fizzle":
            _, _, name, reason = event
            if reason == "overflow":
                margin.append(name)
            elif reason == "duplicate":
                lines.append(f"  {name} again? The duplicate fizzles, but the MP is spent.")
            elif reason == "no_mana":
                lines.append(f"  {name} fizzles: no MP left.")
            elif reason == "empty":
                lines.append(f"  {name}: the satchel is empty.")
        elif kind == "mp":
            _, name, before, after = event
            if margin:
                lines.append(f"  Fizzled in the margin: {', '.join(margin)}.")
            lines.append(f"  {name}'s MP: {before} -> {after}")
        elif kind == "exhausted":
            lines.append(f"  {event[1]} is EXHAUSTED: the next hit lands 1.5x.")
        elif kind == "faint":
            lines.append(f"  {event[1]} faints!")
        elif kind == "scry":
            _, rows_out, ends = event
            lines.append("  Nothing castable here, and no free looks left: the turn is spent."
                         if ends else f"  A free look ({rows_out} rows). No MP spent.")
    lines.append(f"  [{report.status_line()}]")
    return lines


def show_foe_turn(turn: FoeTurn, battle: Battle, out: Out) -> None:
    out("")
    out(f"{battle.state.foe.name}'s book:")
    out(f"  > {turn.sql}")
    for line in page_lines(turn.report) + narrate(turn.report):
        out(line)
    if turn.invitation:
        out("")
        out(f"  *** The word {turn.invitation} glows in the Slime's book. Ada copies the rune: "
            f"{turn.invitation} unlocked! ***")


def show_schema(battle: Battle, out: Out) -> None:
    for (table,) in battle.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"):
        cols = [row[1] for row in battle.conn.execute(f"PRAGMA table_info({table})")]
        out(f"  {table}: {', '.join(cols)}")


def show_reasoning(battle: Battle, out: Out, reasoning: dict | None) -> None:
    if not reasoning:
        out("  The Slime has not thought about anything yet.")
        return
    for key, value in reasoning.items():
        out(f"  {key}: {value}")


# ------------------------------------------------------------------ the loop

def play(battle: Battle, read: Callable[[str], str], out: Out) -> str | None:
    """Run the battle until someone wins or the player quits. Returns the winner."""
    reasoning = None
    shown_round = 0
    while battle.whose_turn != "over":
        if battle.last_round:
            gained = battle.last_round.mp_gained
            out(f"\n-- end of round {battle.last_round.turn}: Ada +{gained['ada']} MP, "
                f"Slime +{gained['foe']} MP --")
            battle.last_round = None
        if battle.state.turn != shown_round:
            shown_round = battle.state.turn
            out(f"\n=== Round {shown_round} ===")
            for line in status(battle):
                out(line)

        if battle.whose_turn == "foe":
            turn = battle.foe_act()
            reasoning = turn.reasoning
            show_foe_turn(turn, battle, out)
            continue

        looks = 3 - battle.state.scries_used
        try:
            sql = read(f"\nAda ({looks} free looks) > ").strip()
        except EOFError:
            return None
        if not sql:
            continue
        if sql in (":q", ":quit"):
            return None
        if sql == ":help":
            out(HELP)
            continue
        if sql == ":why":
            show_reasoning(battle, out, reasoning)
            continue
        if sql == ":schema":
            show_schema(battle, out)
            continue
        try:
            report = battle.ada_cast(sql)
        except Miscast as miscast:
            out(f"  *poof* {miscast}  (Apprentice mode: a miscast is free.)")
            continue
        for line in page_lines(report) + narrate(report):
            out(line)
        if not report.ends_turn:
            for line in status(battle):
                out(line)

    out("")
    for line in status(battle):
        out(line)
    if battle.winner == "ada":
        out("\nThe Asterisk Slime melts into a puddle of rows. Ada wins!")
    else:
        out("\nAda's HP hits zero. The Slime wobbles triumphantly. Game over.")
    return battle.winner


def main(argv: list[str] | None = None, read: Callable[[str], str] = input,
         out: Out = print) -> int:
    parser = argparse.ArgumentParser(description="SQL Witch: fight the Asterisk Slime in SQL.")
    parser.add_argument("--seed", type=int, default=None,
                        help="random seed; the same seed replays the same battle")
    args = parser.parse_args(argv)
    seed = args.seed if args.seed is not None else int(time.time())
    battle = Battle(seed=seed)
    out(f"SQL WITCH - the Tutorial Glade   (seed {seed})\n")
    out(INTRO.format(rows=PAGE_ROWS))
    play(battle, read, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
