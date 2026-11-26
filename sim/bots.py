"""Simulated players (prompt 08 §3, design doc 9.1): they write SQL, the real Battle runs it.

How it works: a bot is called on the protagonist's turn and returns one query. It reads only
what a player could read: the tables (it looks at enemies once to learn the weakness), its own
HP and MP, the guardian's last query in its book. Its queries go through the same pipeline as a
player's. Four levels:

- novice: never limits its query; overflows every turn (the school build's first mistake).
- attack_only: precise and efficient (it learns the weakness, names exactly the spells it can
  pay for) but it only attacks: no heals, no wards, no items. Pressure guardians beat it.
- competent: attacks the same way, and also reads the guardian's book: a telegraphed big spell
  gets a ward first, an Aegis gets the cleansing item, low HP gets a heal, low MP an Ether.
- expert: competent, plus it heals earlier and keeps its streak clean for Focus.

Must not: never import pygame; never touch the battle's rng (bots are deterministic: the seed
alone makes a fight differ); never read the guardian's brain (only its book).

STATUS: four bots, a fight loop, satchel for a first attempt at each guardian.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai.pressure import PRESSURE
from magic.battle import Battle
from magic.guard import Miscast
from magic.rules import SUPER_EFFECTIVE


def quote(names) -> str:
    return ", ".join("'" + n.replace("'", "''") + "'" for n in names)


@dataclass
class Bot:
    name: str = "bot"
    heals: bool = False             # uses heals, wards and items
    reads_book: bool = False        # reacts to the guardian's telegraph and Aegis
    heal_below: float = 0.35
    limits: bool = True             # names only what it can pay for
    known: dict = field(default_factory=dict)

    # ------------------------------------------------------------ what it can read

    def _rows(self, battle: Battle, sql: str) -> list[tuple]:
        try:
            return battle.conn.execute(sql).fetchall()
        except Exception:
            return []

    def spells(self, battle: Battle) -> list[tuple]:
        return self._rows(battle, "SELECT name, element, power, mp_cost, kind FROM spells")

    def items(self, battle: Battle) -> dict[str, tuple]:
        return {r[0]: r for r in self._rows(battle, "SELECT name, kind, amount, qty FROM items")
                if r[3] and r[3] > 0}

    def chart(self, battle: Battle) -> dict:
        return dict(((a, d), m) for a, d, m in
                    self._rows(battle, "SELECT attack, defend, multiplier FROM type_chart"))

    def telegraphed(self, battle: Battle) -> bool:
        spec = PRESSURE.get(battle.guardian.key, {})
        book = battle.state.foe_book
        return bool(book) and spec.get("kind") == "big_turn" and \
            book[-1] == spec.get("telegraph_sql", "").format(foe_id=battle.state.foe_id)

    # ------------------------------------------------------------ the turn

    def __call__(self, battle: Battle) -> str:
        state = battle.state
        if "seen" not in self.known:
            self.known["seen"] = True
            return "SELECT name, element, weakness FROM enemies"      # a free look first
        ada, foe = state.ada, state.foe
        if not self.limits:
            return "SELECT name FROM spells"
        if self.heals:
            move = self.defend(battle)
            if move:
                return move
        return self.attack(battle) or "SELECT * FROM witch"

    def defend(self, battle: Battle) -> str | None:
        ada, foe = battle.state.ada, battle.state.foe
        items = self.items(battle)
        by_kind = {}
        for name, kind, amount, qty in items.values():
            by_kind.setdefault(kind, name)
        spells = {}
        for r in sorted(self.spells(battle), key=lambda r: -r[2]):
            if r[3] <= ada.mp:
                spells.setdefault(r[4], r)                 # the strongest one it can pay for
        if self.reads_book and foe.aegis and "cleanse" in by_kind:
            return f"SELECT name FROM items WHERE name = {quote([by_kind['cleanse']])}"
        if self.reads_book and self.telegraphed(battle) and ada.ward < 15:
            if "ward" in by_kind:
                return f"SELECT name FROM items WHERE name = {quote([by_kind['ward']])}"
            if "ward" in spells:
                return f"SELECT name FROM spells WHERE name = {quote([spells['ward'][0]])}"
        if ada.hp_ratio < self.heal_below:
            if "heal" in spells:
                return f"SELECT name FROM spells WHERE name = {quote([spells['heal'][0]])}"
            if "hp" in by_kind:
                return f"SELECT name FROM items WHERE name = {quote([by_kind['hp']])}"
        if ada.mp < 5 and "mp" in by_kind:
            return f"SELECT name FROM items WHERE name = {quote([by_kind['mp']])}"
        if self.reads_book and foe.aegis:
            return "SELECT name, hp FROM enemies"                     # wait it out: a look
        return None

    def attack(self, battle: Battle) -> str | None:
        state = battle.state
        ada, foe = state.ada, state.foe
        chart = self.chart(battle)
        options = []
        for name, element, power, cost, kind in self.spells(battle):
            if kind not in ("attack", "area"):
                continue
            mult = chart.get((element, foe.element or "Void"), 1.0)
            if foe.relevance and mult < SUPER_EFFECTIVE:
                continue                               # it would bounce off
            options.append((power * mult, cost, name))
        options.sort(key=lambda o: (-o[0] / max(1, o[1]), -o[0]))
        chosen, mp = [], ada.mp
        for value, cost, name in sorted(options, key=lambda o: -o[0]):
            if cost <= mp and len(chosen) < battle.page_rows():
                chosen.append(name)
                mp -= cost
        if not chosen:
            return None
        return f"SELECT name FROM spells WHERE name IN ({quote(chosen)})"


def novice() -> Bot:
    return Bot("novice", limits=False)


def attack_only() -> Bot:
    return Bot("attack_only")


def competent() -> Bot:
    return Bot("competent", heals=True, reads_book=True)


def expert() -> Bot:
    return Bot("expert", heals=True, reads_book=True, heal_below=0.5)


BOTS = {"novice": novice, "attack_only": attack_only, "competent": competent, "expert": expert}


# ------------------------------------------------------------------ fights

def first_attempt_satchel(guardian: str) -> dict[str, int]:
    """What a player carries into a guardian's first attempt: the starting satchel plus what
    the earlier guardians dropped (data/exploration.json)."""
    from ai.roster import ORDER
    from magic.battle import EXPLORATION
    from magic.db import DATA_DIR, read_csv
    satchel = {r["name"]: r["qty"] for r in read_csv(DATA_DIR / "items.csv") if r["qty"]}
    for key in ORDER[:ORDER.index(guardian)] if guardian in ORDER else []:
        for name, qty in EXPLORATION["drops"].get(key, {}).items():
            satchel[name] = satchel.get(name, 0) + qty
    return satchel


def play(guardian: str, bot: Bot, seed: int, max_steps: int = 400, **battle_kwargs) -> Battle:
    """One fight to the end. A query the guard refuses is a wasted turn for the bot."""
    battle_kwargs.setdefault("inventory", first_attempt_satchel(guardian))
    battle = Battle(seed=seed, guardian=guardian, **battle_kwargs)
    for _ in range(max_steps):
        if battle.whose_turn == "over":
            break
        if battle.whose_turn == "ada":
            try:
                battle.ada_cast(bot(battle))
            except Miscast:
                battle.ada_cast("SELECT name FROM spells WHERE name = 'nothing'")
        else:
            battle.foe_act()
    return battle


def win_rate(guardian: str, level: str, seeds=range(200), **battle_kwargs) -> float:
    wins = sum(play(guardian, BOTS[level](), seed, **battle_kwargs).winner == "ada"
               for seed in seeds)
    return wins / len(seeds)
