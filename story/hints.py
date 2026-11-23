"""The Hint Director: decides when someone speaks during Ada's turn, and what they say.

It watches the battle through plain signals: how long Ada has been idle, miscasts in a row, how
often her spells spilled past the page, her HP and MP, the items she still carries and has never
used, the tables she has read (has she ever looked at `enemies`?), the same query cast turn after
turn, the world's integrity, and the guardian brain's own explain() (so a taunt is truthful: the
"{mode}" a guardian boasts about is the mode its brain is really in).

data/hints.json lists topics in order. Each has a condition (the script condition language) and
a ladder of steps: the guardian speaks first, in character, with a taunt that hides a real hint;
if Ada is still stuck the Grimoire steps in, each step more specific (an observation, a nudge, a
concrete query shape, an offer to show the exact query). Every step is a node of
data/story/hints.script, so hints share the dialogue format, its effects and its i18n keys.

Rules: at most one line per turn, then a cooldown; never the same line twice in a fight; silence
while Ada is doing well (quiet_when), except for loud topics (a damaged world, low HP).

Never imports pygame; time is passed in by whoever plays the battle.

STATUS: signals, topics with escalating steps, cooldowns, no repeats, quiet when doing well,
truthful taunts from explain().
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from i18n import CATALOG
from magic.db import DATA_DIR
from story.scenes import text_of
from story.script import Line, evaluate, get, plain


@lru_cache(maxsize=1)
def settings() -> dict:
    with open(DATA_DIR / "hints.json", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Hint:
    """One line to say: who, the text in the current language, and where it came from."""
    topic: str
    node: str
    speaker: str
    key: str
    markup: str                       # inline effects kept, placeholders filled
    turn: int

    @property
    def text(self) -> str:
        return plain(self.markup)


@dataclass
class Signals:
    """What the director has seen in this fight (fed by observe(), miscast(), keystroke())."""
    miscasts: int = 0
    overflows: int = 0
    seen: set = field(default_factory=set)
    same_query: int = 0
    last_sql: str = ""
    last_damage: int = 0
    heal_used: bool = False
    ether_used: bool = False


def mode_of(explain: dict) -> str:
    """The guardian's current mode from its brain's explain(): "opening -> careful" -> careful."""
    return str(explain.get("mode", "")).split("->")[-1].strip()


class HintDirector:
    def __init__(self, guardian: str, data: dict | None = None, script: str | None = None):
        self.guardian = guardian
        self.data = data or settings()
        self.script = get(script or self.data.get("script", "hints"))
        self.signals = Signals()
        self.turn = 0
        self.idle_ms = 0.0
        self.said: set[str] = set()           # nodes already said in this fight
        self.progress: dict[str, int] = {}    # topic -> how many of its steps are done
        self.last_turn: int | None = None     # the turn of the last line
        self.log: list[Hint] = []

    # ------------------------------------------------------------ what happened

    def start_turn(self, turn: int) -> None:
        """Ada's turn begins: the idle clock restarts."""
        self.turn = turn
        self.idle_ms = 0.0

    def keystroke(self) -> None:
        self.idle_ms = 0.0

    def miscast(self) -> None:
        self.signals.miscasts += 1
        self.idle_ms = 0.0

    def observe(self, report) -> None:
        """One of Ada's casts resolved (a magic.cast.CastReport, or anything with its fields)."""
        from magic.tutorial import tables_read     # sqlglot, loaded only once a battle runs
        s = self.signals
        s.miscasts = 0
        self.idle_ms = 0.0
        try:
            s.seen |= tables_read(report.sql)
        except Exception:                          # an odd query reads as no tables
            pass
        if getattr(report, "overflow", 0) > 0:
            s.overflows += 1
        sql = " ".join(report.sql.split()).rstrip(";").lower()
        s.same_query = s.same_query + 1 if sql == s.last_sql else 1
        s.last_sql = sql
        s.last_damage = sum(c.amount for c in getattr(report, "casts", ())
                            if getattr(c, "kind", "") in ("attack", "area"))
        for event in getattr(report, "events", ()):
            if event and event[0] == "item":
                s.heal_used |= event[4] == "hp"
                s.ether_used |= event[4] == "mp"

    # ------------------------------------------------------------ deciding

    def variables(self, context: dict) -> dict:
        s = self.signals
        explain = context.get("explain") or {}
        return {
            "turn": self.turn, "idle": self.idle_ms / 1000, "miscasts": s.miscasts,
            "overflows": s.overflows, "seen": {t: True for t in s.seen},
            "same_query": s.same_query, "last_damage": s.last_damage,
            "heal_used": s.heal_used, "ether_used": s.ether_used,
            "hp": context.get("hp", 1.0), "mp": context.get("mp", 1.0),
            "heals": context.get("heals", 0), "ethers": context.get("ethers", 0),
            "integrity": context.get("integrity", "intact"),
            "foe": {"mode": mode_of(explain), "intent": explain.get("intent", "")},
            "guardian": self.guardian,
        }

    def tick(self, ms: float, context: dict) -> Hint | None:
        """Time passes in Ada's turn. Returns a line to say now, or None (most of the time)."""
        self.idle_ms += ms
        if self.last_turn is not None and \
                self.turn - self.last_turn < max(1, self.data.get("cooldown_turns", 1)):
            return None                            # one line per turn, then the cooldown
        names = self.variables(context)
        quiet = bool(evaluate(self.data["quiet_when"], names)) if self.data.get("quiet_when") \
            else False
        for topic in self.data["topics"]:
            if quiet and not topic.get("loud"):
                continue
            wait = topic.get("idle_s", self.data.get("speak_after_idle_s", 6))
            if names["idle"] < wait or not evaluate(topic["when"], names):
                continue
            node = self._next_step(topic)
            if node is None:
                continue                           # this topic has said all it can
            return self._say(topic["id"], node, names)
        return None

    def _next_step(self, topic: dict) -> str | None:
        steps = topic["steps"]
        done = self.progress.get(topic["id"], 0)
        while done < len(steps):
            node = steps[done].replace("{guardian}", self.guardian)
            if node in self.script.nodes and node not in self.said:
                return node
            done += 1                              # e.g. the dummy has no taunts: skip
            self.progress[topic["id"]] = done
        return None

    def _say(self, topic: str, node: str, names: dict) -> Hint:
        line = next(item for item in self.script.node(node).items if isinstance(item, Line))
        mode = names["foe"]["mode"]
        # The mode in words ("careful", "on the attack"): the brain's real mode, translated.
        args = {"mode": CATALOG.raw(f"hint.mode.{mode}") or mode,
                "intent": names["foe"]["intent"], "guardian": self.guardian}
        markup = CATALOG.format(text_of(line), **args)
        hint = Hint(topic, node, line.speaker, line.key, markup, self.turn)
        self.said.add(node)
        self.progress[topic] = self.progress.get(topic, 0) + 1
        self.last_turn = self.turn
        self.log.append(hint)
        return hint


def context_of(battle) -> dict:
    """The context tick() needs, read from a magic.battle.Battle (no SQL the player sees)."""
    state = battle.state
    ada = state.ada
    counts = {"hp": 0, "mp": 0}
    try:
        for kind, qty in battle.conn.execute("SELECT kind, qty FROM items"):
            if kind in counts and isinstance(qty, int) and qty > 0:
                counts[kind] += qty
    except Exception:                              # the items table may be gone: none left
        pass
    explain = battle.brain.explain() if hasattr(battle.brain, "explain") else {}
    return {"hp": ada.hp_ratio,
            "mp": ada.mp / ada.max_mp if ada.max_mp else 0.0,
            "heals": counts["hp"], "ethers": counts["mp"],
            "integrity": state.integrity, "explain": explain or {}}


def all_keys() -> dict[str, str]:
    return get(settings().get("script", "hints")).keys()

