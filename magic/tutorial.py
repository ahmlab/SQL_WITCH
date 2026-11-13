"""The tutorial's lessons: what the Grimoire says, when a lesson passes, how hints grow.

This is the brain of the tutorial scene, kept free of pygame so it can be tested headless.
The scene only draws what `strip()` returns, types the demo, and feeds this class the player's
queries, the passing time and the key presses.

How it works:
- The script is data (data/tutorial.json): lessons, wording, ghost levels, hint thresholds.
- Every query, the Grimoire's demo included, goes through the real Battle against a real foe
  row, the Training Dummy (ai/dummy.py). Nothing is parsed or scripted here.
- A lesson passes on what the query DID (its CastReport), never on how it was typed: any
  query that meets the goal passes, and a valid query that misses it is coached, not refused.
- There are no stakes: the dummy owns no spells, MP is refilled, the dummy re-stuffs itself,
  and looks never run out during the lessons.
- A stuck player (idle, or failing) climbs a ladder of hints that never goes back down.
Never imports pygame.

STATUS: script loading and checking, goals, phases, coaching, hint ladder, ghost text, records.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from sqlglot import exp

from magic import guard
from magic.battle import Battle
from magic.cast import PAGE_ROWS, CastReport, sync_state
from magic.db import DATA_DIR
from magic.guard import Miscast

# How much text each box of the tutorial screen holds (characters per line, lines). The scene
# lays its boxes out from these numbers, and load_script() refuses a line that does not fit.
STRIP_CHARS, STRIP_LINES = 46, 2          # the Grimoire's instruction strip
WRITE_CHARS = STRIP_CHARS - 2             # a query shown under it, after "> "
DUMMY_CHARS, DUMMY_LINES = 26, 2          # the dummy's speech bubble
KEYS_CHARS = 76                           # the reminder at the bottom of the book
QUEST_CHARS = 42                          # one checklist line, after its check mark

GHOST_MODES = ("none", "hint", "keywords", "word", "full")     # from least to most help
GOAL_KEYS = {"look", "from", "visible", "spells_cast"}
REVEALS = {"ada_panel", "foe_panel", "status", "looks", "tables_button", "guide_button"}
POINTS = {"row", "cell", "column", "header", "right_edge", "cast_rows", "cut_row", "status",
          "mp_bar", "foe_hp", "tables_button", "guide_button", "ready_button"}
TALK_PHASES = ("opening", "intro", "after", "success", "ending")
GHOST_KEYWORDS = {"SELECT", "FROM"}
SAMPLE = {"rows": 12, "cast": 4, "lost": 8, "page": PAGE_ROWS, "mp_before": 30, "mp_after": 0,
          "rune": "ORDER BY"}             # typical values, to measure lines with placeholders


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap, the same rule as engine.grimoire.wrap (kept here to stay pygame-free;
    a test checks the two agree on every line of the script)."""
    lines, line = [], ""
    for word in text.split():
        while len(word) > width:
            if line:
                lines.append(line)
                line = ""
            lines.append(word[:width])
            word = word[width:]
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= width:
            line += " " + word
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# ------------------------------------------------------------------ the script

@dataclass(frozen=True)
class Step:
    """One thing on screen: a line of the Grimoire and what goes with it."""
    say: str = ""
    write: str = ""                  # a query shown under the line, in query colours
    hint: str = ""                   # ingredients shown under the line instead of a query
    point: str = ""                  # what to circle, e.g. "cell:weakness:0"
    dummy: str = ""                  # the dummy's reply
    refill: bool = False             # the Grimoire refills Ada's MP when this step starts
    reveal: tuple[str, ...] = ()     # parts of the screen this step uncovers
    narrator: bool = False           # not spoken by the Grimoire


def _step(data: dict, report: CastReport | None = None) -> Step:
    fill = _numbers(report) if report else {}
    text = data.get("say", "")
    return Step(say=text.format(**fill) if fill else text, write=data.get("write", ""),
                hint=data.get("hint", ""), point=data.get("point", ""),
                dummy=data.get("dummy", ""), refill=bool(data.get("refill")),
                reveal=tuple(data.get("reveal", ())), narrator=bool(data.get("narrator")))


def _numbers(report: CastReport) -> dict:
    """The placeholders a line may use, read from the real result."""
    return {"rows": len(report.rows), "cast": len(report.casts), "lost": report.overflow,
            "page": PAGE_ROWS, "mp_before": report.mp_before, "mp_after": report.mp_after}


def _check_text(problems: list[str], where: str, text: str, chars: int, lines: int) -> None:
    try:
        text = text.format(**SAMPLE)
    except (KeyError, IndexError, ValueError) as error:
        problems.append(f"{where}: unknown placeholder ({error})")
        return
    got = wrap(text, chars)
    if len(got) > lines or any(len(line) > chars for line in got):
        problems.append(f"{where}: does not fit {lines} line(s) of {chars} characters: {text!r}")


def _check_step(problems: list[str], where: str, step: dict) -> None:
    under = bool(step.get("write") or step.get("hint"))
    if "say" in step:
        _check_text(problems, f"{where}.say", step["say"], STRIP_CHARS,
                    STRIP_LINES - 1 if under else STRIP_LINES)
    if step.get("write"):
        _check_text(problems, f"{where}.write", step["write"], WRITE_CHARS, 1)
    if step.get("hint"):
        _check_text(problems, f"{where}.hint", step["hint"], STRIP_CHARS, 1)
    if step.get("dummy"):
        _check_text(problems, f"{where}.dummy", step["dummy"], DUMMY_CHARS, DUMMY_LINES)
    if step.get("point") and step["point"].split(":")[0] not in POINTS:
        problems.append(f"{where}.point: unknown target {step['point']!r}")
    for part in step.get("reveal", ()):
        if part not in REVEALS:
            problems.append(f"{where}.reveal: unknown part {part!r}")


def _check_goal(problems: list[str], where: str, goal: dict) -> None:
    for key in set(goal) - GOAL_KEYS:
        problems.append(f"{where}.goal: unknown condition {key!r}")


def script_problems(script: dict) -> list[str]:
    """Everything wrong with a script, in words the person editing the file can act on."""
    problems: list[str] = []
    for i, step in enumerate(script.get("opening", [])):
        _check_step(problems, f"opening[{i}]", step)
    for lesson in script["lessons"] + [script["practice"]]:
        where = lesson["id"]
        _check_text(problems, f"{where}.keys", lesson["keys"], KEYS_CHARS, 1)
        for part in lesson.get("reveal", ()):
            if part not in REVEALS:
                problems.append(f"{where}.reveal: unknown part {part!r}")
        for key in ("intro", "demo_after", "success"):
            for i, step in enumerate(lesson.get(key, [])):
                _check_step(problems, f"{where}.{key}[{i}]", step)
        task = dict(lesson["task"])
        if lesson.get("hint"):
            task["hint"] = lesson["hint"]
        _check_step(problems, f"{where}.task", task)
        if "example" in lesson:
            if lesson.get("ghost") not in GHOST_MODES:
                problems.append(f"{where}.ghost: must be one of {', '.join(GHOST_MODES)}")
            _check_goal(problems, where, lesson["goal"])
            for key in ("restate", "off_goal"):
                _check_step(problems, f"{where}.{key}",
                            {"say": lesson[key], "write": lesson["example"]})
        for quest in lesson.get("quests", []):
            _check_text(problems, f"{quest['id']}.label", quest["label"], QUEST_CHARS, 1)
            _check_goal(problems, quest["id"], quest["goal"])
            _check_step(problems, f"{quest['id']}.done", quest["done"])
        if "all_done" in lesson:
            _check_step(problems, f"{where}.all_done", lesson["all_done"])
    for i, step in enumerate(script.get("ending", [])):
        _check_step(problems, f"ending[{i}]", step)
    for key, text in script["coach"].items():
        if not key.startswith("_"):
            _check_text(problems, f"coach.{key}", text, STRIP_CHARS, 1)
    for key, lines in script["dummy"].items():
        if key.startswith("_") or key == "name":
            continue
        for text in ([lines] if isinstance(lines, str) else lines):
            _check_text(problems, f"dummy.{key}", text, DUMMY_CHARS, DUMMY_LINES)
    for key in ("idle_ms", "failed_tries"):
        levels = script["hints"][key]
        if len(levels) != 3 or sorted(levels) != list(levels):
            problems.append(f"hints.{key}: three rising numbers, one per hint level")
    return problems


def load_script(path: Path | str = DATA_DIR / "tutorial.json") -> dict:
    """Read the script, and refuse one whose lines would not fit the screen."""
    with open(path, encoding="utf-8") as f:
        script = json.load(f)
    problems = script_problems(script)
    if problems:
        raise ValueError("data/tutorial.json needs fixing:\n  " + "\n  ".join(problems))
    return script


# ------------------------------------------------------------------ goals

def _tree(sql: str):
    try:
        return guard.parse_one_select(sql)
    except Miscast:
        return None


def tables_read(sql: str) -> set[str]:
    """The tables a query reads, from its syntax tree (not from its text)."""
    tree = _tree(sql)
    return {table.name.lower() for table in tree.find_all(exp.Table)} if tree else set()


def _asks_for(sql: str, column: str) -> bool:
    """Did the query really ask for this column? (SELECT hp AS weakness did not.)"""
    tree = _tree(sql)
    if tree is None:
        return False
    if next(tree.find_all(exp.Star), None) is not None:
        return True
    return column in {c.name.lower() for c in tree.find_all(exp.Column)}


def _has_from(tree) -> bool:
    # sqlglot renamed the key from "from" to "from_" in recent versions; accept both.
    return tree.args.get("from_") is not None or tree.args.get("from") is not None


def spells_cast(report: CastReport) -> int:
    """Ada's spells that took effect (a potion is not a spell)."""
    return sum(1 for cast in report.casts if cast.kind != "item" and not cast.deflected)


def goal_met(goal: dict, report: CastReport) -> bool:
    """Judge a goal on the result of a query. See the vocabulary in data/tutorial.json."""
    if goal.get("look") and not report.scry:
        return False
    if "from" in goal and goal["from"].lower() not in tables_read(report.sql):
        return False
    readable = {report.columns[i].lower() for i in report.visible_columns}
    for column in goal.get("visible", ()):
        column = column.lower()
        if column not in readable or not report.rows or not _asks_for(report.sql, column):
            return False
    return spells_cast(report) >= goal.get("spells_cast", 0)


# ------------------------------------------------------------------ ghost text

def _tokens(text: str) -> list[str]:
    return text.replace(",", " , ").split()


def ghost_text(example: str, typed: str, mode: str) -> tuple[str, bool]:
    """(the faded text to offer after `typed`, whether `typed` already is the whole example).

    The player is following the example while every word typed so far matches it, ignoring
    case and spacing. Off that path nothing is offered: the ghost guides, it never judges."""
    want, have = _tokens(example), _tokens(typed)
    if len(have) > len(want):
        return "", False
    partial = ""
    for i, word in enumerate(have):
        target = want[i]
        if word.lower() == target.lower():
            continue
        mid_word = i == len(have) - 1 and typed[-1:].strip() != ""
        if mid_word and target.lower().startswith(word.lower()):
            partial = target[len(word):]
            if word.islower():
                partial = partial.lower()
        else:
            return "", False
    rest = want[len(have):]
    if not rest and not partial:
        return "", True
    # The player's case: "sel" or "select" means the rest of the keywords come in lowercase.
    if any(w.isalpha() and w.islower() and any(k.lower().startswith(w) for k in GHOST_KEYWORDS)
           for w in have):
        rest = [w.lower() if w in GHOST_KEYWORDS else w for w in rest]
    if mode == "keywords":                  # finish or offer a keyword, never a name
        if partial:
            rest = []
            if want[len(have) - 1].upper() not in GHOST_KEYWORDS:
                partial = ""
        else:
            rest = rest[:1] if rest and rest[0].upper() in GHOST_KEYWORDS else []
    elif mode == "word":
        rest = [] if partial else rest[:1]
    elif mode != "full":
        return "", False
    text = partial + "".join(("" if word == "," else " ") + word for word in rest)
    if not typed or typed[-1].isspace():
        text = text.lstrip()
    return text, False


# ------------------------------------------------------------------ the tutorial

@dataclass
class Outcome:
    """What one of the player's queries led to. The scene shows it; nothing is decided there."""
    kind: str                         # pass | off_goal | early_cast | miscast | locked | quest | free
    report: CastReport | None = None
    message: str = ""                 # the game's own miscast line, for the right page
    dummy: str = ""                   # what the dummy says about it
    restuffed: bool = False           # the dummy was hit and put its straw back
    quest: str = ""                   # the quest this query completed


class Tutorial:
    """One run of the tutorial. `phase` says what is happening:

    opening  the Grimoire greets (talk)       intro    it introduces a lesson (talk)
    demo     it types and casts the example   after    it explains its own result (talk)
    task     the player's turn                success  it celebrates (talk)
    ending   it sets up the first guardian    done     the tutorial is over

    Talk phases move on with advance(). The last lesson is free practice: it stays in `task`
    until ready()."""

    def __init__(self, seed: int, script: dict | None = None):
        self.script = script if script is not None else load_script()
        self.seed = seed
        # foe_opens=False and a speed of 0 in foes.csv: Ada always acts first.
        self.battle = Battle(seed=seed, guardian="dummy", foe_opens=False)
        self.chatter = random.Random(seed)       # picks the dummy's lines; not the battle's rng
        self.lessons: list[dict] = self.script["lessons"] + [self.script["practice"]]
        self.index = -1
        self.phase = "opening"
        self.step: Step | None = None
        self.revealed: set[str] = set()
        self.passed: list[str] = []
        self.quests_done: list[str] = []
        self.records: list[dict] = []            # one per lesson, for the playtest log
        self.coach: Step | None = None           # a reaction that replaces the task line
        self.last_report: CastReport | None = None
        self._talk: list[Step] = []
        self._last_quip = ""
        self._reset_counters()
        self._say([_step(s) for s in self.script.get("opening", [])])
        if self.step is None:
            self._start_lesson(0)

    # ------------------------------------------------------------ reading the state

    @property
    def lesson(self) -> dict | None:
        return self.lessons[self.index] if 0 <= self.index < len(self.lessons) else None

    @property
    def practising(self) -> bool:
        return self.lesson is not None and "quests" in self.lesson

    @property
    def done(self) -> bool:
        return self.phase == "done"

    @property
    def titles(self) -> list[str]:
        """The progress marks: one per lesson that has something to pass."""
        return [lesson["title"] for lesson in self.script["lessons"]]

    @property
    def keys(self) -> str:
        return self.lesson["keys"] if self.lesson else ""

    @property
    def demo_query(self) -> str:
        """What the Grimoire types during the demo phase."""
        return self.lesson["example"] if self.phase == "demo" else ""

    @property
    def hint_level(self) -> int:
        """0 to 3. It only ever rises within a lesson."""
        return self._level

    @property
    def ghost_mode(self) -> str:
        """How much faded text the page offers now: the lesson's level, raised by the hints."""
        if self.phase != "task" or self.practising:
            return "none"
        floor = {2: "word", 3: "full"}.get(self._level, "none")
        return max(self.lesson["ghost"], floor, key=GHOST_MODES.index)

    def next_step(self, text: str) -> tuple[str, str]:
        """(faded text to insert, advice to show) for the editor, while a lesson is on."""
        if self.phase != "task" or self.practising:
            return "", ""
        insert, complete = ghost_text(self.lesson["example"], text, self.ghost_mode)
        return insert, (self.script["coach"]["cast_hint"] if complete else "")

    def strip(self) -> Step:
        """What the Grimoire's strip shows right now."""
        if self.phase != "task":
            return self.step or Step()
        if self.coach is not None:
            return self.coach
        lesson, coach = self.lesson, self.script["coach"]
        if self.practising:
            all_done = len(self.quests_done) == len(lesson["quests"])
            return _step(lesson["all_done"] if all_done else lesson["task"])
        if self._level >= 3:
            return Step(say=coach["offer"], write=lesson["example"])
        if self._level == 2:
            return Step(say=coach["ghost_word"], write=lesson["example"])
        if self._level == 1:
            return Step(say=lesson["restate"], write=lesson["example"])
        return _step({**lesson["task"], "hint": lesson.get("hint", "")})

    # ------------------------------------------------------------ talking

    def _say(self, steps: list[Step]) -> None:
        self._talk = list(steps)
        self.step = None
        if self._talk:
            self._enter(self._talk.pop(0))

    def _enter(self, step: Step) -> None:
        self.step = step
        self.revealed |= set(step.reveal)
        if step.refill:
            self._refill()

    def advance(self) -> Step | None:
        """The player confirmed a line: the next line, or the next phase. Returns the new
        line, if any. Does nothing while a query is expected."""
        if self.phase not in TALK_PHASES:
            return None
        if self._talk:
            self._enter(self._talk.pop(0))
            return self.step
        match self.phase:
            case "opening":
                self._start_lesson(0)
            case "intro":
                if self.practising:
                    self._start_task()
                else:
                    self.phase = "demo"              # the last intro line stays on screen
            case "after":
                self._start_task()
            case "success":
                self._record("passed")
                self.passed.append(self.lesson["id"])
                self._start_lesson(self.index + 1)
            case "ending":
                self.phase, self.step = "done", None
        return self.step

    def _start_lesson(self, index: int) -> None:
        self.index = index
        self._reset_counters()
        self._reset_world()
        self.revealed |= set(self.lesson.get("reveal", ()))
        self.phase = "intro"
        self._say([_step(s, self.last_report) for s in self.lesson["intro"]])

    def _start_task(self) -> None:
        self._reset_world()                         # every task starts with full MP
        self.phase, self.step, self.coach = "task", None, None
        self._idle = 0

    # ------------------------------------------------------------ the world has no stakes

    def _refill(self) -> None:
        ada = self.battle.state.ada
        ada.mp, ada.exhausted = ada.max_mp, False
        sync_state(self.battle.conn, self.battle.state)

    def _reset_world(self) -> None:
        state = self.battle.state
        state.foe.hp = state.foe.max_hp
        state.scries_used = 0
        self._refill()

    def _settle(self, report: CastReport) -> bool:
        """After any query: let the dummy take its turn, and undo what would be a stake.
        Returns whether the dummy had to put its straw back."""
        state = self.battle.state
        if report.ends_turn:
            self.battle.foe_act()                   # it stands still: a real, harmless look
            state.ada.mp = report.mp_after          # no silent regeneration: refills are shown
        if not self.practising:
            state.scries_used = 0                   # during the lessons, looks never run out
        restuffed = state.foe.hp < state.foe.max_hp
        state.foe.hp = state.foe.max_hp             # one cast can never bring it down
        sync_state(self.battle.conn, state)
        self.last_report = report
        return restuffed

    # ------------------------------------------------------------ the Grimoire's demo

    def cast_demo(self) -> CastReport:
        """The Grimoire casts the lesson's example, through the same path as the player."""
        if self.phase != "demo":
            raise RuntimeError(f"No demo to cast now ({self.phase}).")
        report = self.battle.ada_cast(self.lesson["example"])
        self._settle(report)
        self.phase = "after"
        self._say([_step(s, report) for s in self.lesson["demo_after"]])
        return report

    # ------------------------------------------------------------ the player's queries

    def cast(self, sql: str) -> Outcome:
        """The player cast a query. It runs for real; then the lesson reacts."""
        if self.phase != "task":
            raise RuntimeError(f"No query is expected now ({self.phase}).")
        self._queries.append(sql)
        self._idle = 0
        try:
            report = self.battle.ada_cast(sql)
        except Miscast as miscast:
            return self._miscast(sql, str(miscast))
        restuffed = self._settle(report)
        outcome = self._practice(report) if self.practising else self._judge(report)
        outcome.restuffed = restuffed
        if not outcome.dummy:
            outcome.dummy = self._reaction(report)
        return outcome

    def _miscast(self, sql: str, message: str) -> Outcome:
        self._miscasts += 1
        coach = self.script["coach"]
        rune = self._locked_rune(sql)
        if self.practising:
            line = coach["locked_rune"].format(rune=rune) if rune else coach["practice_miscast"]
            self.coach = Step(say=line)
        else:
            self._fail()
            line = coach["locked_rune"].format(rune=rune) if rune else coach["miscast"]
            self.coach = Step(say=line, write=self.lesson["example"])
        return Outcome("locked" if rune else "miscast", message=message,
                       dummy=self._quip("miscast"))

    def _locked_rune(self, sql: str) -> str:
        """The first rune in the query that Ada has not learned, or '' (read from the syntax
        tree, the same way the guard does, not from the miscast's wording)."""
        tree = _tree(sql)
        if tree is None:
            return ""
        locked = guard.runes_used(tree) - self.battle.state.ada.runes
        return sorted(locked)[0] if locked else ""

    def _judge(self, report: CastReport) -> Outcome:
        lesson, coach = self.lesson, self.script["coach"]
        if goal_met(lesson["goal"], report):
            self.phase, self.coach = "success", None
            self._say([_step(s, report) for s in lesson["success"]])
            return Outcome("pass", report, dummy=self.step.dummy if self.step else "")
        self._off_goal += 1
        self._fail()
        if lesson["goal"].get("look") and report.casts:
            # Spells or potions went off in a lesson about looking: no harm, and no lecture.
            self._refill()
            self.coach = Step(say=coach["cast_too_early"], write=lesson["example"], refill=True)
            return Outcome("early_cast", report)
        self.coach = Step(say=lesson["off_goal"], write=lesson["example"])
        return Outcome("off_goal", report)

    def _practice(self, report: CastReport) -> Outcome:
        coach = self.script["coach"]
        self.coach = None
        if report.mp_spent:                         # free practice: mana is free too
            self._refill()
            self.coach = Step(say=coach["refill"], point="mp_bar", refill=True)
        elif report.scry and report.ends_turn:      # the fourth look of a turn
            self.coach = Step(say=coach["looks_spent"])
        for quest in self.lesson["quests"]:
            if quest["id"] not in self.quests_done and goal_met(quest["goal"], report):
                self.quests_done.append(quest["id"])
                self.coach = _step(quest["done"], report)
                return Outcome("quest", report, dummy=self.coach.dummy, quest=quest["id"])
        return Outcome("free", report)

    def _reaction(self, report: CastReport) -> str:
        """The dummy has opinions about being hit or stared at."""
        foe = self.battle.state.foe.name
        if any(cast.target == foe and cast.damage for cast in report.casts):
            return self._quip("hit")
        if report.scry and "enemies" in tables_read(report.sql):
            return self._quip("looked_at")
        return ""

    def _quip(self, kind: str) -> str:
        lines = [line for line in self.script["dummy"][kind] if line != self._last_quip]
        self._last_quip = self.chatter.choice(lines)
        return self._last_quip

    def restuffed_line(self) -> str:
        return self.script["dummy"]["restuffed"]

    # ------------------------------------------------------------ nobody stays stuck

    def _reset_counters(self) -> None:
        self._level = 0
        self._coach_level = 0
        self._idle = 0                 # ms without a key press, during a task
        self._failed = 0               # miscasts and off-goal queries in this lesson
        self._miscasts = 0
        self._off_goal = 0
        self._ms = 0                   # time spent in this lesson, all phases
        self._queries: list[str] = []
        self.coach = None

    def _raise_level(self) -> None:
        hints = self.script["hints"]
        by_idle = sum(self._idle >= limit for limit in hints["idle_ms"])
        by_tries = sum(self._failed >= limit for limit in hints["failed_tries"])
        level = max(self._level, by_idle, by_tries)
        if level > self._level:
            self._level = level
            if self.coach is not None and by_idle > self._coach_level:
                self.coach = None       # waiting did not help: the stronger hint takes over

    def _fail(self) -> None:
        self._failed += 1
        self._raise_level()
        self._coach_level = self._level

    def tick(self, dt: int) -> None:
        """Time passes (ms). Only an idle task raises the hint level."""
        if self.phase == "done":
            return
        self._ms += dt
        if self.phase == "task" and not self.practising:
            self._idle += dt
            self._raise_level()

    def activity(self) -> None:
        """A key was pressed: the player is not stuck, just writing."""
        self._idle = 0
        if self.practising and self.phase == "task":
            self.coach = None           # in free practice a reaction lasts until the next key

    def on_enter(self, text: str) -> bool:
        """ENTER was pressed in the editor. If the query looked finished, the Grimoire says
        how to cast it (the controls do not change). Returns whether it spoke."""
        if self.phase != "task":
            return False
        tree = _tree(text.strip()) if text.strip() else None
        if tree is None or not _has_from(tree):
            return False
        example = "" if self.practising else self.lesson["example"]
        self.coach = Step(say=self.script["coach"]["enter"], write=example)
        return True

    # ------------------------------------------------------------ leaving

    def ready(self) -> bool:
        """READY: leave free practice for the ending. Only works there."""
        if not (self.practising and self.phase == "task"):
            return False
        self._record("ready")
        self.phase, self.coach = "ending", None
        self._say([_step(s) for s in self.script["ending"]])
        return True

    def skip(self) -> None:
        """The player chose to skip: the tutorial ends at once."""
        if self.phase == "done":
            return
        self._record("skipped")
        self.phase, self.step, self.coach = "done", None, None

    def _record(self, result: str) -> None:
        self.records.append({
            "lesson": self.lesson["id"] if self.lesson else "opening", "result": result, "seconds": round(self._ms / 1000, 1),
            "miscasts": self._miscasts, "off_goal": self._off_goal,
            "hint_level": self._level, "queries": list(self._queries), "seed": self.seed})
