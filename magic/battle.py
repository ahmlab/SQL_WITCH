"""One battle, round by round (design doc 4.1). Shared by the terminal game and the window.

The battle is a small step machine instead of a loop, so the pygame scene can drive it one
event at a time and the terminal can drive it with input(). Either way the order is:
the guardian opens the first round (so the player reads a query before writing one), and
the turns then alternate strictly; Ada may scry up to SCRY_PER_TURN times, then casts one query;
the foe perceives, decides, writes its SQL and casts it; then the round ends.
Never imports pygame.

Since sandbox v2 (plan §4.1) the battle also owns the World (magic/world.py): before each of
Ada's casts it snapshots the database, after every cast it asks the World what changed, applies
the reactions' effects (a foe enraged or confused, a refused query undone) and records new
techniques in the Codex. Ada may Rewind to a snapshot; it costs her turn. A world left broken
until the end of the round ends the fight in confusion: no winner, no reward.

STATUS: guardians, turn order, the World (snapshots, Rewind, reactions, tricks), the Codex,
Scrolls, confused foes, the confused ending.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass

from ai.base import CONFUSED_SQL
from ai.roster import GUARDIANS, Guardian
from magic import guard, rules
from magic.cast import CastReport, load_state, resolve, sync_state
from magic.db import build_db
from magic.guard import Miscast
from magic.spellbook import Spellbook
from magic.world import Reaction, World
from story.codex import Codex


@dataclass
class FoeTurn:
    """What the foe did. The intent is not kept: only the SQL and its result matter."""
    sql: str
    report: CastReport
    reasoning: dict              # brain.explain(), for the F1 overlay
    invitation: str | None       # a technique the foe's book just showed Ada (its Codex page)
    movement: object = None      # the brain's steering order (ai.steering.Movement), if any
    acknowledged: str | None = None   # the foe's technique, which Ada already knew
    confused: bool = False       # the foe could not cast: its book is gone or unreadable


@dataclass
class RoundEnd:
    """What happened at the end of a round, for the renderer."""
    turn: int                    # the round that just ended
    mp_gained: dict[str, int]
    winner: str | None


class Battle:
    def __init__(self, seed: int, guardian: str = "slime", brain=None,
                 ada_runes: set[str] | None = None, level: int | None = None,
                 foe_opens: bool = True, codex: Codex | None = None,
                 scrolls: dict[str, str] | None = None):
        self.guardian: Guardian = GUARDIANS[guardian]
        g = self.guardian
        # One random generator for the whole battle: same seed, same battle (design doc 5.10).
        self.rng = random.Random(seed)
        self.seed = seed
        self.conn = guard.harden(build_db(level or g.level, foe_ids=[g.foe_id]))
        self.state = load_state(self.conn, foe_id=g.foe_id, seed=seed)
        # The Glade assumes nothing beyond SELECT and FROM; each guardian then adds its rune.
        self.state.ada.runes = set(g.ada_runes if ada_runes is None else ada_runes)
        self.state.foe.runes = set(g.runes)
        self.chart = rules.load_type_chart(self.conn)
        self.brain = brain if brain is not None else g.make_brain(self.conn)
        self.foe_opens = foe_opens
        self.turn_order: list[str] | None = None
        self.foe_turns = 0
        self.winner: str | None = None
        self.queue: list[str] = []
        self.last_round: RoundEnd | None = None
        self.codex = codex if codex is not None else Codex()
        self.spellbook = Spellbook(self.conn, scrolls)
        self.world = World(self.conn, self.state)
        self.rewards: list[dict] = []          # tricks rewarded in this fight
        self.broken_round: int | None = None   # the round the world broke in, if it is broken
        self._start_round()

    # ------------------------------------------------------------ whose turn

    @property
    def whose_turn(self) -> str:
        """'ada', 'foe' or 'over'."""
        return "over" if self.winner else self.queue[0]

    def _start_round(self) -> None:
        # The order is settled once, in round 1, and then strictly alternates. Re-deciding
        # it every round would let the faster side act twice in a row across the boundary
        # (last in round 1, first in round 2).
        if self.turn_order is None:
            if self.foe_opens:
                first = "foe"      # the guardian teaches by example: its query comes first
            else:
                first = rules.first_mover(self.state, self.rng)
            self.turn_order = [first, "foe" if first == "ada" else "ada"]
        self.queue = list(self.turn_order)
        rules.start_turn(self.state, self.queue[0])

    def _advance(self) -> None:
        """The current side is done: check for a winner, then pass the turn or end the round."""
        self.winner = rules.winner(self.state)
        if self.winner:
            return
        self.queue.pop(0)
        if self.queue:
            rules.start_turn(self.state, self.queue[0])
            return
        before = {"ada": self.state.ada.mp, "foe": self.state.foe.mp}
        turn = self.state.turn
        # A world that stays broken (the foe deleted, never rewound) cannot host a fight. Ada
        # always gets one more turn to rewind; if the world is still broken at the end of the
        # next round, the fight dissolves in confusion and the Codex suggests backups.
        if self.state.ending == "confused" or self.state.integrity == "broken":
            if self.broken_round is None:
                self.broken_round = turn
            elif turn > self.broken_round:
                self.winner = "confused"
                self.codex.unlock("backups")
                self.last_round = RoundEnd(turn, {"ada": 0, "foe": 0}, self.winner)
                return
        else:
            self.broken_round = None
        self.winner = rules.end_of_round(self.state)
        gained = {"ada": self.state.ada.mp - before["ada"],
                  "foe": self.state.foe.mp - before["foe"]}
        self.last_round = RoundEnd(turn, gained, self.winner)
        sync_state(self.conn, self.state)      # the regenerated MP must be visible to queries
        if not self.winner:
            self._start_round()

    # ------------------------------------------------------------ the two sides

    def explain(self, sql: str) -> tuple[list[str], int]:
        """The query plan SQLite chose (SCAN, SEARCH ... USING INDEX) and how many rows the
        scanned tables hold: the statistics screen shows rows scanned against rows returned.
        Only for a read; it runs nothing (EXPLAIN never touches the data)."""
        try:
            plan = [row[3] for row in self.conn.execute(f"EXPLAIN QUERY PLAN {sql}")]
        except Exception:
            return [], 0
        scanned = 0
        for step in plan:
            words = step.split()
            if len(words) >= 2 and words[0] == "SCAN" and words[1].isidentifier():
                try:
                    scanned += self.conn.execute(f'SELECT COUNT(*) FROM "{words[1]}"').fetchone()[0]
                except Exception:
                    pass
        return plan, scanned

    def ada_cast(self, sql: str) -> CastReport:
        """Ada's query. Raises guard.Miscast for a rejected query; in Apprentice mode a miscast
        is free, so her turn simply continues. A scry does not end the turn either."""
        if self.whose_turn != "ada":
            raise RuntimeError(f"It is not Ada's turn ({self.whose_turn}).")
        self.last_round = None
        snap = self.world.snapshot(self.state)                 # the way back, taken first
        try:
            report = resolve(self.conn, self.state, sql, "ada", self.rng, self.chart)
        except Miscast:
            self.world.discard(snap)                           # nothing happened
            raise
        found = self.world.assess("player", report.statements, report.outcome, report)
        if found.refusal is not None or found.duplicate:
            # The world refuses this one (the witch's own row, a name used twice): undo it all.
            self.state = self._restore(snap)
            self.world.discard(snap)
            if found.duplicate:
                raise Miscast("miscast.duplicate_name", name=found.duplicate)
            raise Miscast(found.refusal.line_key)
        self._apply(found, report)
        for technique in sorted(report.runes):                 # the Codex remembers
            if self.codex.record(technique, sql, self.state.turn):
                report.codex.append(technique)
            self.state.ada.runes.add(technique)
        self.spellbook.note(sql, bool(report.casts))
        if report.scry and not report.ends_turn and not found.changes:
            self.world.discard(snap)                           # a free look changes nothing
        else:
            snap.summary_key, snap.summary_args = _summary(report)
        self.state.ada_casts.append(self._remember(report))   # what the foe can perceive
        if report.ends_turn:
            self._advance()
        return report

    # ------------------------------------------------------------ the world's consequences

    def _restore(self, snap) -> rules.BattleState:
        state = self.world.restore(snap)
        self.world.state = state
        sync_state(self.conn, state)
        return state

    def _apply(self, found, report: CastReport) -> None:
        """Turn the World's reactions into effects, and record them on the report."""
        state = self.state
        state.integrity, state.missing = found.integrity, found.missing
        for reaction in found.reactions:
            match reaction.effect:
                case "foe_rages":
                    state.foe_rage = True
                case "foe_forgets":
                    state.foe_forgets = True
                case "fight_ends_confused":
                    state.ending = "confused"
                case "forget_chart":
                    self.chart = {}                            # every element hits normally
                case "codex_unlock":
                    if reaction.page and self.codex.unlock(reaction.page):
                        report.codex.append(reaction.page)
        for trick in found.tricks:
            reward = dict(trick["reward"], trick=trick["id"])
            self.rewards.append(reward)
            if reward.get("codex") and self.codex.unlock(reward["codex"]):
                report.codex.append(reward["codex"])
            report.tricks.append(Reaction(trick["id"], trick["speaker"], trick["line_key"],
                                          "none"))
        report.reactions = list(found.reactions)
        report.integrity = found.integrity

    def rewind(self, index: int) -> CastReport:
        """Turn the world back to snapshot `index`: the database and the battle state. It costs
        Ada's turn, it is written in query_log, and the guardian comments on it."""
        if self.whose_turn != "ada":
            raise RuntimeError(f"It is not Ada's turn ({self.whose_turn}).")
        snap, state = self.world.rewind(index)
        state.scries_used = 0
        self.broken_round = None
        self.state = state
        self.world.state = state
        self.spellbook.ensure_views()                          # Scrolls outlive time travel
        sync_state(self.conn, state)
        try:
            self.conn.execute("INSERT INTO query_log (turn, caster, sql, clauses, rows_out, "
                              "rows_cast, seed) VALUES (?, ?, ?, 'REWIND', 0, 0, ?)",
                              (state.turn, state.ada.name, f"-- REWIND to turn {snap.turn}",
                               state.rng_seed))
        except Exception:
            pass
        found = self.world.assess("player", extra=("rewind",))
        report = CastReport(sql=f"-- REWIND to turn {snap.turn}", caster="ada", columns=[],
                            rows=[], visible=0, visible_columns=[], runes=frozenset(),
                            mp_before=state.ada.mp, kind="rewind")
        report.events.append(("rewind", snap.turn))
        self._apply(found, report)
        self.last_round = None
        self._advance()
        return report

    def _remember(self, report: CastReport) -> rules.CastMemory:
        foe = self.state.foe.name
        hits = [c for c in report.casts if c.kind in ("attack", "area") and c.target == foe]
        return rules.CastMemory(
            turn=self.state.turn, runes=tuple(sorted(report.runes)),
            elements=tuple(c.element for c in report.casts if c.element),
            damage=sum(c.damage for c in hits),
            super_effective=any(c.effective >= rules.SUPER_EFFECTIVE for c in hits),
            overflow=report.overflow, scry=report.scry)

    def foe_act(self) -> FoeTurn:
        """The foe's five-stage loop (design doc 5.1): perceive, decide, express, execute, reveal."""
        if self.whose_turn != "foe":
            raise RuntimeError(f"It is not the foe's turn ({self.whose_turn}).")
        self.last_round = None
        self.foe_turns += 1
        snapshot = copy.deepcopy(self.state)                  # perceive: a copy it cannot change
        intent = self.brain.decide(snapshot, self.rng)        # decide
        reasoning = self.brain.explain()
        movement = getattr(self.brain, "movement", None)
        if intent.kind == "confused":                         # express
            sql = CONFUSED_SQL
        else:
            sql = self.guardian.style(intent, self.state, self.foe_turns)
        del intent                                            # from here on only the SQL counts
        confused = False
        try:
            report = resolve(self.conn, self.state, sql, "foe", self.rng, self.chart)  # execute
        except Miscast:
            # Its book is gone or reshaped: it stares at an empty page, and its turn is spent.
            confused = True
            self.state.foe_book.append(sql)
            report = CastReport(sql=sql, caster="foe", columns=[], rows=[], visible=0,
                                visible_columns=[], runes=frozenset(), mp_before=self.state.foe.mp,
                                scry=True, kind="read")
            report.events.append(("confused", self.state.foe.name))
        found = self.world.assess("foe", report=report)
        self._apply(found, report)
        invitation, acknowledged = self._invitation(report)   # reveal
        self._advance()
        return FoeTurn(sql, report, reasoning, invitation, movement, acknowledged, confused)

    def _invitation(self, report: CastReport) -> tuple[str | None, str | None]:
        """The foe's book shows its signature technique (design doc 3.6). If Ada has not used it
        yet, the Codex records the demonstration (taught); if she has, it is acknowledged."""
        rune = self.guardian.signature
        if not rune or rune not in report.runes:
            return None, None
        if rune in self.state.ada.runes:
            return None, rune
        self.state.ada.runes.add(rune)
        if self.codex.demonstrate(rune, report.sql, self.guardian.key, self.state.turn):
            report.codex.append(rune)
        return rune, None


def _summary(report: CastReport) -> tuple[str, dict]:
    """One line for the Rewind page: what the cast after this snapshot did."""
    for statement in report.statements:
        if statement.kind in ("write", "schema") and statement.target:
            return f"world.summary.{statement.verb}", {"table": statement.target}
    if report.kind == "transaction":
        return "world.summary.transaction", {}
    if report.casts:
        return "world.summary.cast", {}
    return "world.summary.read", {}
