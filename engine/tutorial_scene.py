"""The tutorial on screen: the Grimoire leads the player through their first queries.

TutorialScene is a BattleScene against the Training Dummy, so the editor, the Grimoire's pages,
the narration, the sparks and the sounds are the battle's own. What it adds:
- the Grimoire's instruction strip (top left) and the dummy's speech bubble;
- the demo: the Grimoire types the lesson's query itself, letter by letter, and casts it;
- progressive disclosure: panels, buttons and counters appear when a lesson introduces them;
- highlights around what the Grimoire is talking about, and progress marks;
- READY (F5) in free practice, and ESC to skip after a confirmation.
Every decision (what to say, when a lesson passes, how much help to give) is made by
magic.tutorial.Tutorial, which knows nothing about pygame; this scene only draws it and feeds
it the player's keys, queries and the passing time.

STATUS: strip, bubble, demo typing, reveals, highlights, progress, READY and skip.
"""

from __future__ import annotations

import pygame

from engine import gfx

import i18n                                # i18n.t: "t" is the tutorial in this file

from engine import render, scenery
from engine.grimoire import LOOKS_AT, wrap
from engine.scenes import (GROUND_SHADOW, GUIDE_BUTTON, TABLES_BUTTON, ADA_FEET, BattleScene,
                           draw_backdrop, draw_protagonist, draw_slime, is_cast_key,
                           is_confirm_key)
from engine.textinput import STYLE_COLOURS, colour_styles
from ai import steering
from magic.tutorial import STRIP_CHARS, TALK_PHASES, Step, Tutorial

STRIP = pygame.Rect(4, 4, 194, 20)            # the Grimoire's instructions; grows downwards
BUBBLE = pygame.Rect(204, 16, 112, 19)        # the dummy's speech, above its head
PROGRESS_AT = (202, 5)                        # the lesson dots, top right
READY_BUTTON = GUIDE_BUTTON                   # READY sits where GUIDE will appear at the end
DEMO_MS_PER_CHAR = 70                         # how fast the Grimoire types its demo
DEMO_PAUSE_MS = 450                           # a breath between typing and casting
BUBBLE_MS = 3200                              # how long a reaction stays over the dummy
PULSE_MS = 1300                               # how long a newly revealed part glows


class TutorialScene(BattleScene):
    PLACE = "tutorial"
    # The dummy's HP panel goes mid-field: the strip and the bubble use the top of the screen.
    FOE_PANEL = pygame.Rect(64, 56, 120, 20)

    def relocalise(self) -> None:
        self.tutorial.relocalise()

    def _time_lessons(self) -> None:
        """How long each lesson took (telemetry, only with consent: lesson id and seconds)."""
        index = self.tutorial.index
        seen = getattr(self, "_lesson_at", None)
        if seen is None or seen[0] != index:
            if seen is not None and 0 <= seen[0] < len(self.tutorial.lessons):
                self.game.track("lesson", lesson=self.tutorial.lessons[seen[0]]["id"],
                                seconds=round((self.time - seen[1]) / 1000, 1))
            self._lesson_at = (index, self.time)
    DANGER_MUSIC = False                     # nothing is at stake here
    HINTS = False                            # the coach is the only voice in practice

    def __init__(self, game, tutorial: Tutorial | None = None):
        self.tutorial = tutorial or Tutorial(seed=game.seed, ada_name=i18n.CATALOG.player["name"])
        super().__init__(game, "dummy", battle=self.tutorial.battle)
        self.beats.clear()                       # no battle tip: the Grimoire is talking
        self.order = steering.Movement("hold")   # a dummy stands still
        self.editor.guide = self._ghost
        self.confirm_skip = False
        self.bubble = ""
        self.bubble_until = 0
        self.demo_typed = 0
        self.demo_clock = 0
        self.pulses: dict[str, int] = {}         # part -> when it was revealed
        self._seen_phase = ""
        self._seen_step: Step | None = None
        self._seen_revealed: set[str] = set()
        self._watch()

    # ------------------------------------------------------------ the editor's faded text

    def _ghost(self, text: str) -> tuple[str, str] | None:
        t = self.tutorial
        if t.phase == "task" and t.practising:
            return None                          # free practice: the usual help
        return t.next_step(text)

    # ------------------------------------------------------------ following the tutorial

    def _watch(self) -> None:
        """React to what changed in the tutorial: a new phase, line or revealed part."""
        t = self.tutorial
        self.phase = "input" if t.phase == "task" else "wait"
        if t.phase != self._seen_phase:
            self._seen_phase = t.phase
            self._enter_phase(t.phase)
            if t.done:
                return
        for part in sorted(t.revealed - self._seen_revealed):
            self.pulses[part] = self.time
            self.game.audio.play("rune")
        self._seen_revealed = set(t.revealed)
        step = t.strip()
        if step != self._seen_step:
            self._seen_step = step
            if step.refill:                      # the Grimoire refills Ada's MP: show it
                self.game.audio.play("mp_up")
                bar = self._mp_bar()
                self.fx.burst(bar.centerx, bar.centery, count=12, speed=50,
                              colours=(render.SKY, render.WHITE, render.BLUE))
            if step.dummy:
                self._say_dummy(step.dummy, BUBBLE_MS * 2)

    def _flush_beats(self) -> None:
        """Finish the narration at once: a new demo or task must not show the old one's bars."""
        queued = self.beats                      # the current beat's effect already ran
        self.beats, self.beat, self.beat_left = [], None, 0
        bubble = self.bubble, self.bubble_until
        for beat in queued:
            if beat.effect:
                beat.effect()
        self.bubble, self.bubble_until = bubble  # an old remark would be out of place now
        self._sync_shown()
        self.bars = {side: [float(v) for v in values] for side, values in self.shown.items()}

    def _enter_phase(self, phase: str) -> None:
        if phase in ("demo", "task"):
            self._flush_beats()
        if phase == "demo":                      # the Grimoire writes on a clean page
            self.editor.clear()
            self.grimoire.clear()
            self.demo_typed, self.demo_clock = 0, 0
        elif phase == "task":                    # ...and clears it for the player
            self.editor.clear()
            self.grimoire.clear()
        elif phase == "done":
            self._leave()

    def _leave(self) -> None:
        """Off to the first guardian."""
        self.game.switch(BattleScene(self.game, "slime"))

    def _advance(self) -> None:
        """ENTER, SPACE or a click on the strip while the Grimoire talks."""
        t = self.tutorial
        if t.phase == "demo":                    # impatient: finish the demo's typing now
            rest = t.demo_query[self.demo_typed:]
            self.editor.insert(rest)
            self.demo_typed += len(rest)
            self.demo_clock = DEMO_PAUSE_MS
            return
        if t.phase in TALK_PHASES:
            self.game.audio.play("next")
            t.advance()
            self._watch()

    def _say_dummy(self, text: str, ms: int = BUBBLE_MS) -> None:
        self.bubble, self.bubble_until = text, self.time + ms

    # ------------------------------------------------------------ the demo

    def _update_demo(self, dt: int) -> None:
        t = self.tutorial
        if t.phase != "demo":
            return
        query = t.demo_query
        self.demo_clock += dt
        while self.demo_typed < len(query) and self.demo_clock >= DEMO_MS_PER_CHAR:
            self.demo_clock -= DEMO_MS_PER_CHAR
            # The demo types through the real editor, so it sparks and chimes like the player.
            event = pygame.event.Event(pygame.TEXTINPUT, text=query[self.demo_typed])
            before = self.editor.text
            self.editor.handle_event(event)
            self._typing_feedback(event, before)
            self.demo_typed += 1
        if self.demo_typed >= len(query) and self.demo_clock >= DEMO_PAUSE_MS:
            x, y = self.grimoire.cursor_xy()
            self.fx.burst(x, y, count=14, speed=80)
            self._show(t.cast_demo())
            self._watch()

    # ------------------------------------------------------------ casting

    def _show(self, report) -> None:
        self.game.audio.play("scry" if report.scry else "cast")
        self._ada_casts(report)
        self.grimoire.show_result(report, self.time, 3 - self.battle.state.scries_used)
        self.narrate(report)

    def cast(self, sql: str) -> None:
        """The player cast a query (BattleScene.handle calls this on CTRL+ENTER)."""
        self._flush_beats()                      # the last query's story is over
        outcome = self.tutorial.cast(sql)
        if outcome.report is None:
            self.grimoire.show_miscast(outcome.message, self.time)
            self.game.audio.play("miscast")
        else:
            self._show(outcome.report)
        if outcome.dummy:
            self._say_dummy(outcome.dummy)
        if outcome.restuffed:                    # after the hits, the straw goes back in
            line = self.tutorial.restuffed_line()
            self.say("", 1, lambda: self._say_dummy(line))
        if outcome.kind == "pass":
            self.say("", 1, None, "invitation")
        elif outcome.kind == "quest":
            self.game.audio.play("rune")
        self._watch()

    # ------------------------------------------------------------ input

    def toggle_tables(self) -> None:
        if "tables_button" in self.tutorial.revealed:
            super().toggle_tables()

    def toggle_rewind(self) -> None:
        """No Rewind in practice: the tutorial already puts the world back after every query."""

    def save_scroll(self) -> None:
        """Scrolls are for real fights; the tutorial's queries are not memorised."""

    def toggle_guide(self) -> None:
        if "guide_button" in self.tutorial.revealed:
            super().toggle_guide()

    def click(self, x: int, y: int) -> None:
        t = self.tutorial
        if self.confirm_skip:
            return
        if self.speech_waiting():
            self.advance_speech()
            return
        if t.practising and t.phase == "task" and READY_BUTTON.collidepoint(x, y):
            self._ready()
        elif self._strip_rect().collidepoint(x, y) and t.phase in TALK_PHASES + ("demo",):
            self._advance()
        elif GUIDE_BUTTON.collidepoint(x, y) and "guide_button" not in t.revealed:
            return
        elif TABLES_BUTTON.collidepoint(x, y) and "tables_button" not in t.revealed:
            return
        else:
            super().click(x, y)

    def _ready(self) -> None:
        if self.tutorial.ready():
            self.game.audio.play("confirm")
            self._watch()

    def handle(self, event):
        if self.speech_key(event):                  # someone speaks: ENTER first
            return
        t = self.tutorial
        key = event.key if event.type == pygame.KEYDOWN else None
        if self.confirm_skip:                    # "Skip the tutorial?" ENTER skips, ESC stays
            if is_confirm_key(event):
                self.confirm_skip = False
                t.skip()
                self._watch()
            elif key == pygame.K_ESCAPE:
                self.confirm_skip = False
            return
        if self.guide.open or self.tables_open or \
                self._is_scroll_key(event) or event.type == pygame.MOUSEWHEEL:
            super().handle(event)                # their own keys, ESC included
            return
        if key == pygame.K_ESCAPE:
            self.confirm_skip = True
            self.game.audio.play("scry")
            return
        if key == pygame.K_F5:
            self._ready()
            return
        if t.phase != "task":                    # the Grimoire is talking or typing
            if is_confirm_key(event) or is_cast_key(event):
                self._advance()
            return
        if event.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
            t.activity()
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER) and not is_cast_key(event):
            if t.on_enter(self.editor.text):     # the controls stay; the Grimoire explains
                self._watch()
        super().handle(event)

    # ------------------------------------------------------------ time

    def update(self, dt):
        # Not BattleScene.update: there are no turns to run, the tutorial settles each query.
        self.time += dt
        self._time_lessons()
        self._update_beats(dt)
        self._update_visuals(dt)
        self._update_ada(dt)
        self._update_body(dt)
        self.fx.update(dt)
        if self.beat is None and not self.beats:
            self._sync_shown()                   # refills and re-stuffing glide into view
        if not self.confirm_skip:
            self.tutorial.tick(dt)
        self._update_demo(dt)
        self._watch()

    # ------------------------------------------------------------ where things are

    def _mp_bar(self) -> pygame.Rect:
        return pygame.Rect(self.ADA_PANEL.x + 14, self.ADA_PANEL.y + 18, 70, 5)

    def _part(self, part: str) -> pygame.Rect | None:
        """A part of the screen the tutorial reveals or points at."""
        g = self.grimoire
        kind, _, rest = part.partition(":")
        match kind:
            case "ada_panel":
                return self.ADA_PANEL.copy()
            case "foe_panel":
                return self.FOE_PANEL.copy()
            case "mp_bar":
                return self._mp_bar()
            case "foe_hp":
                return pygame.Rect(self.FOE_PANEL.x + 14, self.FOE_PANEL.y + 11, 100, 5)
            case "looks":
                return LOOKS_AT.copy()
            case "tables_button":
                return TABLES_BUTTON.copy()
            case "guide_button" | "ready_button":
                return GUIDE_BUTTON.copy()
            case "row":
                return g.spot("row", row=int(rest or 0))
            case "cell":
                column, _, row = rest.partition(":")
                return g.spot("cell", column, int(row or 0))
            case "column":
                return g.spot("column", rest)
            case _:
                return g.spot(kind)

    # ------------------------------------------------------------ drawing

    def draw(self, canvas):
        t, revealed = self.tutorial, self.tutorial.revealed
        draw_backdrop(canvas)
        hx, hy = self.foe_xy()
        gfx.ellipse(canvas, GROUND_SHADOW, (hx - 12, hy + 14, 24, 6))
        scenery.draw_dummy(canvas, (hx, hy), self.time,
                           self.flash["foe"] > 0 and (self.time // 40) % 2 == 0)
        if t.phase == "ending" and t.step is not None and t.step.narrator:
            draw_slime(canvas, (304, 50), self.time, False, False, False)   # it peeks in
        draw_protagonist(self.game, canvas, ADA_FEET,
                         self.flash["ada"] > 0 and (self.time // 40) % 2 == 0,
                 anim=self.ada)
        if "foe_panel" in revealed:
            self._draw_foe_panel(canvas)
        if "ada_panel" in revealed:
            self._draw_ada_panel(canvas)
        self._draw_bubble(canvas)
        self._draw_narration(canvas)

        g = self.grimoire
        g.show_looks = "looks" in revealed
        g.show_status = "status" in revealed
        g.footer = t.keys
        g.draw(canvas, self.time, focused=t.phase == "task" and not self.confirm_skip)
        self._draw_page_heat(canvas)
        self.fx.draw(canvas)

        self._draw_strip(canvas)
        self._draw_progress(canvas)
        if "tables_button" in revealed:
            self._draw_tables_button(canvas)
        if "guide_button" in revealed:
            self._draw_guide_button(canvas)
        elif t.practising and t.phase == "task":
            self._draw_ready_button(canvas)
        self._draw_highlights(canvas)
        self._draw_speech(canvas)                     # over the lesson, under the overlays
        if self.tables_open:
            self._draw_tables(canvas)
        if self.game.debug:
            self._draw_debug(canvas)
        self.guide.draw(canvas, self.time)
        if self.confirm_skip:
            self._draw_skip(canvas)

    def _strip_lines(self) -> tuple[Step, list[str], list[tuple[str, str]], list[dict]]:
        t = self.tutorial
        step = t.strip()
        under = [("write", step.write)] if step.write else \
            [("hint", step.hint)] if step.hint else []
        quests = t.lesson["quests"] if t.practising and t.phase == "task" else []
        return step, wrap(step.say, STRIP_CHARS), under, quests

    def _strip_rect(self) -> pygame.Rect:
        _, lines, under, quests = self._strip_lines()
        rows = max(1, len(lines) + len(under) + len(quests))
        return pygame.Rect(STRIP.x, STRIP.y, STRIP.width, 6 + rows * render.LINE_H)

    def _draw_strip(self, canvas):
        f, t = render.font(), self.tutorial
        step, lines, under, quests = self._strip_lines()
        box = self._strip_rect()
        render.panel(canvas, box, border=render.VIOLET)
        x, y = box.x + 4, box.y + 3
        for line in lines:
            f.draw(canvas, line, (x, y), render.SLATE if step.narrator else render.INK)
            y += render.LINE_H
        for kind, text in under:
            if kind == "write":                  # the query to type, in the editor's colours
                f.draw(canvas, ">", (x, y), render.AMBER)
                styles = colour_styles(text, set(), set(self.editor.names))
                render.draw_coloured(canvas, text, [STYLE_COLOURS[s] for s in styles],
                                     (x + 2 * render.ADVANCE, y))
            else:
                f.draw(canvas, text, (x, y), render.TEAL)
            y += render.LINE_H
        for quest in quests:
            done = quest["id"] in t.quests_done
            f.draw(canvas, ("[*] " if done else "[ ] ") + quest["label"], (x, y),
                   render.FOREST if done else render.SLATE)
            y += render.LINE_H
        if t.phase in TALK_PHASES and (self.time // 400) % 2 == 0:
            f.draw(canvas, "v", (box.right - 7, box.bottom - 8), render.VIOLET)

    def _draw_progress(self, canvas):
        f, t = render.font(), self.tutorial
        x, y = PROGRESS_AT
        ids = [lesson["id"] for lesson in t.script["lessons"]]
        for i, lesson_id in enumerate(ids):
            dot = pygame.Rect(x + i * 7, y, 5, 5)
            done = lesson_id in t.passed or (i == t.index and t.phase == "success")
            gfx.rect(canvas, render.INK, dot.inflate(2, 2))
            if done:
                gfx.rect(canvas, render.GOLD, dot)
            elif i == t.index and (self.time // 300) % 2 == 0:
                gfx.rect(canvas, render.LAVENDER, dot)
            else:
                gfx.rect(canvas, render.SLATE, dot)
        if t.lesson is not None:
            f.draw(canvas, t.lesson["title"], (x + len(ids) * 7 + 2, y - 1), render.BUTTER,
                   shadow=render.INK)

    def _draw_ready_button(self, canvas):
        f = render.font()
        glowing = (self.time // 400) % 2 == 0
        render.panel(canvas, READY_BUTTON, fill=render.BUTTER if glowing else render.CREAM)
        f.draw(canvas, i18n.t("tutorial_ui.ready"), (READY_BUTTON.x + 8, READY_BUTTON.y + 3), render.FOREST)

    def _draw_bubble(self, canvas):
        if not self.bubble or self.time > self.bubble_until:
            return
        f = render.font()
        lines = wrap(self.bubble, 26)[:2]
        box = pygame.Rect(BUBBLE.x, BUBBLE.y, BUBBLE.width, 5 + len(lines) * render.LINE_H)
        render.panel(canvas, box)
        # A small pointer under the bubble, above the dummy's head.
        x = min(max(render.snap(self.body.position.x), box.x + 6), box.right - 6)
        tail = [(x - 3, box.bottom - 1), (x + 3, box.bottom - 1), (x, box.bottom + 3)]
        gfx.polygon(canvas, render.CREAM, tail)
        gfx.line(canvas, render.INK, tail[0], tail[2])
        gfx.line(canvas, render.INK, tail[1], tail[2])
        for i, line in enumerate(lines):
            f.draw(canvas, line, (box.x + 4, box.y + 3 + i * render.LINE_H), render.BARK)

    def _draw_highlights(self, canvas):
        """Circle what the Grimoire is talking about; make newly revealed parts glow."""
        point = self.tutorial.strip().point
        rect = self._part(point) if point else None
        if rect is not None:
            colour = render.GOLD if (self.time // 250) % 2 == 0 else render.RED
            gfx.rect(canvas, colour, rect.inflate(4, 4), 1)
            for corner in (rect.inflate(4, 4).topleft, rect.inflate(4, 4).bottomright):
                gfx.rect(canvas, colour, (corner[0] - 1, corner[1] - 1, 3, 3))
        for part, born in list(self.pulses.items()):
            age = self.time - born
            if age > PULSE_MS:
                del self.pulses[part]
                continue
            area = self._part(part)
            if area is not None:
                grow = 2 + (age // 160) % 3
                colour = render.WHITE if (age // 120) % 2 == 0 else render.LILAC
                gfx.rect(canvas, colour, area.inflate(grow * 2, grow * 2), 1)

    def _draw_skip(self, canvas):
        f = render.font()
        text = self.tutorial.script["coach"]["skip"]
        render.cover(canvas, canvas.get_rect(), (*render.INK, 170))
        box = pygame.Rect(0, 0, f.width(text) + 16, 17)
        box.center = (160, 70)
        render.cover(canvas, box, (*render.INK, 255))
        render.cover(canvas, box.inflate(-2, -2), (*render.CREAM, 255))
        f.draw(canvas, text, (box.x + 8, box.y + 5), render.INK)
