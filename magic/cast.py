"""The page split and the Casting Contract: turns a query result into spells (design doc 3.2-3.4).

Player and foe queries take exactly the same path:
guard.inspect() -> guard.run_query() -> split_page() -> casting contract -> resolve -> query_log.
Power, cost and element always come from the tables, never from the query, so the only way
to hurt someone is to make a real query return a real spell name.

STATUS: step 2 done - page split, casting contract, Rule of the Page, scrying, query_log.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from magic import guard, rules
from magic.rules import BattleState, Combatant

# Tuning constants from design doc 3.3. Change them here, never inline.
PAGE_ROWS = 4            # how many rows the right page can show
PAGE_WIDTH = 36          # how many characters fit across the right page
SCRY_PER_TURN = 3        # free looks before Ada must commit
COLUMN_GAP = 1           # characters between two columns when the table is printed


# ------------------------------------------------------------------ the page

@dataclass
class Page:
    """How a result fits on the Grimoire's right page."""
    visible_rows: list[tuple]
    hidden_rows: list[tuple]
    visible_columns: list[int]     # indexes of the columns that fit entirely
    widths: list[int]              # printed width of every column, in characters


def cell_text(value) -> str:
    """How a cell is printed. The renderer and the width rule must agree on this."""
    return "NULL" if value is None else str(value)


def column_widths(columns: list[str], rows: list[tuple]) -> list[int]:
    # Every row counts, not only the visible ones: the table is printed whole, then clipped.
    widths = [len(name) for name in columns]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(cell_text(value)))
    return widths


def split_page(columns: list[str], rows: list[tuple]) -> Page:
    """Cut a result at PAGE_ROWS rows and PAGE_WIDTH characters."""
    widths = column_widths(columns, rows)
    visible_columns, x = [], 0
    for i, width in enumerate(widths):
        if x + width > PAGE_WIDTH:
            break                  # this column is clipped, and so is everything to its right
        visible_columns.append(i)
        x += width + COLUMN_GAP
    return Page(visible_rows=list(rows[:PAGE_ROWS]), hidden_rows=list(rows[PAGE_ROWS:]),
                visible_columns=visible_columns, widths=widths)


# ------------------------------------------------------------------ the catalogues

@dataclass(frozen=True)
class Spell:
    name: str
    element: str
    power: int
    mp_cost: int
    kind: str              # attack | heal | ward | area


@dataclass(frozen=True)
class Item:
    name: str
    kind: str              # hp | mp
    amount: int
    qty: int


def spellbook(conn, state: BattleState, caster: str) -> dict[str, Spell]:
    """The spells this caster knows, read from the canonical table (contract clause 4)."""
    if caster == "ada":
        rows = conn.execute("SELECT name, element, power, mp_cost, kind FROM spells")
    else:
        rows = conn.execute("SELECT name, element, power, mp_cost, kind FROM foe_spells "
                            "WHERE foe_id = ?", (state.foe_id,))
    return {row[0]: Spell(*row) for row in rows}


def satchel(conn, caster: str) -> dict[str, Item]:
    """Items belong to Ada; foes have none in this build."""
    if caster != "ada":
        return {}
    rows = conn.execute("SELECT name, kind, amount, qty FROM items")
    return {row[0]: Item(*row) for row in rows}


# ------------------------------------------------------------------ the report

@dataclass
class Cast:
    """One row that took effect."""
    row: int
    spell: str             # spell or item name
    target: str            # combatant name
    kind: str              # attack | area | heal | ward | item
    damage: int = 0
    crit: bool = False
    effective: float = 1.0 # type-chart multiplier: 2.0 is super effective
    amount: int = 0        # HP healed, ward gained or MP restored


@dataclass
class Fizzle:
    """One castable row that did nothing."""
    row: int
    name: str
    reason: str            # overflow | no_mana | duplicate | empty
    mp_paid: int


@dataclass
class CastReport:
    sql: str
    caster: str                        # "ada" or "foe"
    columns: list[str]
    rows: list[tuple]
    visible: int                       # rows printed on the page
    visible_columns: list[int]
    runes: set[str]                    # technique signature from the rune gate
    casts: list[Cast] = field(default_factory=list)
    fizzles: list[Fizzle] = field(default_factory=list)
    overflow: int = 0                  # castable rows nobody could read
    mp_before: int = 0
    mp_spent: int = 0
    scry: bool = False
    ends_turn: bool = True
    events: list[tuple] = field(default_factory=list)

    @property
    def mp_after(self) -> int:
        return self.mp_before - self.mp_spent

    def status_line(self) -> str:
        """The line under the Grimoire page: '11 rows | 4 cast | 7 lost | MP 30 -> 0'."""
        return (f"{len(self.rows)} rows | {len(self.casts)} cast | {self.overflow} lost | "
                f"MP {self.mp_before} -> {self.mp_after}")


def effect_word(multiplier: float) -> str:
    if multiplier > 1:
        return "super effective"
    if multiplier < 1:
        return "not very effective"
    return ""


# ------------------------------------------------------------------ the contract

@dataclass
class _Row:
    """What the contract found in one result row, before MP is paid."""
    index: int
    name: str
    column: int
    spell: Spell | None
    item: Item | None
    target: str | None     # side named in the row ("ada" / "foe"), if any


def _read_row(index: int, row: tuple, book: dict, items: dict,
              names: dict[str, str]) -> _Row | None:
    """Clauses 2 and 3: the first spell or item name casts, a combatant name targets."""
    action, target = None, None
    for column, value in enumerate(row):
        if not isinstance(value, str):
            continue
        if action is None and (value in book or value in items):
            action = (value, column)
        elif target is None and value in names:
            target = names[value]
    if action is None:
        return None                    # clause 5: information only
    name, column = action
    return _Row(index, name, column, book.get(name), items.get(name), target)


def _default_target(kind: str, caster: str) -> str:
    # Attacks go to the other side; heals and wards go to the caster (clause 3).
    return caster if kind in ("heal", "ward") else ("foe" if caster == "ada" else "ada")


def _cost(plan: _Row) -> int:
    return plan.spell.mp_cost if plan.spell else 0


def _apply_spell(plan: _Row, me: Combatant, target: Combatant, chart: dict,
                 rng: random.Random, report: CastReport) -> None:
    spell = plan.spell
    if spell.kind in ("attack", "area"):
        hit = rules.damage(spell.power, spell.element, target, chart, rng)
        rules.apply_hit(target, hit)
        report.casts.append(Cast(plan.index, spell.name, target.name, spell.kind,
                                 damage=hit.amount, crit=hit.crit, effective=hit.multiplier))
        report.events.append(("cast", plan.index, me.name, spell.name, target.name,
                              hit.amount, hit.crit, hit.multiplier))
        if not target.alive:
            report.events.append(("faint", target.name))
    elif spell.kind == "heal":
        amount = rules.heal(target, spell.power)
        report.casts.append(Cast(plan.index, spell.name, target.name, "heal", amount=amount))
        report.events.append(("heal", plan.index, spell.name, target.name, amount))
    elif spell.kind == "ward":
        amount = rules.add_ward(target, spell.power)
        report.casts.append(Cast(plan.index, spell.name, target.name, "ward", amount=amount))
        report.events.append(("ward", plan.index, spell.name, target.name, amount))


def _use_item(conn, plan: _Row, target: Combatant, report: CastReport) -> None:
    item = plan.item
    if item.kind == "mp":
        amount = rules.restore_mp(target, item.amount)
    else:
        amount = rules.heal(target, item.amount)
    conn.execute("UPDATE items SET qty = qty - 1 WHERE name = ?", (item.name,))
    report.casts.append(Cast(plan.index, item.name, target.name, "item", amount=amount))
    report.events.append(("item", plan.index, item.name, target.name, item.kind, amount))


def _fizzle(report: CastReport, plan: _Row, reason: str, paid: int) -> None:
    report.fizzles.append(Fizzle(plan.index, plan.name, reason, paid))
    report.events.append(("fizzle", plan.index, plan.name, reason))


def resolve(conn, state: BattleState, sql: str, caster: str, rng: random.Random,
            chart: dict | None = None) -> CastReport:
    """Run one query for 'ada' or 'foe' and apply the Casting Contract.

    Raises guard.Miscast for a rejected query; nothing changes in that case.
    """
    me = state.side(caster)
    runes = guard.inspect(sql, me.runes)
    columns, rows = guard.run_query(conn, sql)
    page = split_page(columns, rows)
    chart = chart if chart is not None else rules.load_type_chart(conn)

    report = CastReport(sql=sql, caster=caster, columns=columns, rows=rows,
                        visible=len(page.visible_rows), visible_columns=page.visible_columns,
                        runes=runes, mp_before=me.mp)
    if caster == "foe":
        state.foe_book.append(sql)

    book, items = spellbook(conn, state, caster), satchel(conn, caster)
    names = {state.ada.name: "ada", state.foe.name: "foe"}
    plans = [p for i, row in enumerate(rows) if (p := _read_row(i, row, book, items, names))]

    if not plans:
        _scry(state, caster, report)
    else:
        _cast(conn, state, caster, plans, page, chart, rng, report)

    _log(conn, state, me, report)
    sync_state(conn, state)
    return report


def _scry(state: BattleState, caster: str, report: CastReport) -> None:
    """Clause 5 / design doc 3.4: a result with nothing castable is a free look."""
    report.scry = True
    if caster == "ada" and state.scries_used < SCRY_PER_TURN:
        state.scries_used += 1
        report.ends_turn = False
    # A foe's query always ends its turn; Ada's fourth look is spent as her cast.
    report.events.append(("scry", len(report.rows), report.ends_turn))


def _cast(conn, state, caster, plans, page, chart, rng, report) -> None:
    """The Rule of the Page: pay for every castable row, act only on the readable ones."""
    me = state.side(caster)
    seen = set()
    for plan in plans:
        cost = _cost(plan)
        paid = min(cost, me.mp)
        me.mp -= paid
        report.mp_spent += paid
        readable = plan.index < PAGE_ROWS and plan.column in page.visible_columns
        target_side = plan.target or _default_target(
            plan.spell.kind if plan.spell else "heal", caster)
        pair = (plan.name, target_side)

        if not readable:
            report.overflow += 1
            _fizzle(report, plan, "overflow", paid)
        elif paid < cost:
            _fizzle(report, plan, "no_mana", paid)    # MP ran dry: the rest fizzle
        elif pair in seen:
            _fizzle(report, plan, "duplicate", paid)  # clause 6, still costs MP
        elif plan.item and plan.item.qty - _used(report, plan.name) <= 0:
            _fizzle(report, plan, "empty", paid)
        elif plan.item:
            _use_item(conn, plan, state.side(target_side), report)
        else:
            _apply_spell(plan, me, state.side(target_side), chart, rng, report)
        if readable:
            seen.add(pair)

    report.events.append(("mp", me.name, report.mp_before, me.mp))
    if report.overflow:
        report.events.append(("overflow", report.overflow))
        if me.mp == 0:
            # Its own overflow drained it dry: wide open until it acts again (design doc 5.3).
            me.exhausted = True
            report.events.append(("exhausted", me.name))


def _used(report: CastReport, name: str) -> int:
    """How many of an item this same query already used (the catalogue was read before)."""
    return sum(1 for c in report.casts if c.kind == "item" and c.spell == name)


# ------------------------------------------------------------------ the world's memory

def _log(conn, state: BattleState, me: Combatant, report: CastReport) -> None:
    conn.execute(
        "INSERT INTO query_log (turn, caster, sql, clauses, rows_out, rows_cast, seed) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (state.turn, me.name, report.sql, ",".join(sorted(report.runes)), len(report.rows),
         len(report.casts), state.rng_seed))


def sync_state(conn, state: BattleState) -> None:
    """Copy HP, MP and wards back into the tables, so the next query reads the truth."""
    ada, foe = state.ada, state.foe
    conn.execute("UPDATE witch SET hp = ?, mp = ?, ward = ? WHERE name = ?",
                 (ada.hp, ada.mp, ada.ward, ada.name))
    conn.execute("UPDATE enemies SET hp = ?, mp = ? WHERE id = ?",
                 (foe.hp, foe.mp, state.foe_id))
    conn.commit()


def load_state(conn, foe_id: int = 1, seed: int = 0) -> BattleState:
    """Build the battle state from a fresh database (magic.db.build_db)."""
    name, hp, max_hp, mp, max_mp, regen, speed, element, ward = conn.execute(
        "SELECT name, hp, max_hp, mp, max_mp, mp_regen, speed, element, ward FROM witch"
    ).fetchone()
    ada = Combatant(name, hp, max_hp, mp, max_mp, regen, speed, element, None, ward or 0)
    fname, fhp, fmax_hp, fmp, fmax_mp, felement, fweak, fspeed = conn.execute(
        "SELECT name, hp, max_hp, mp, max_mp, element, weakness, speed FROM enemies "
        "WHERE id = ?", (foe_id,)).fetchone()
    # A NULL hp is hidden from queries but tracked by the engine (design doc, Appendix B).
    foe = Combatant(fname, fhp if fhp is not None else fmax_hp, fmax_hp, fmp, fmax_mp,
                    rules.FOE_MP_REGEN, fspeed, felement, fweak)
    return BattleState(ada=ada, foe=foe, rng_seed=seed, foe_id=foe_id)
