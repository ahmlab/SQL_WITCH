"""Scenes: Title -> Dialogue -> Battle -> Result, as a small state machine (design doc 6.2).

Scenes only draw and react to input. Every rule lives in magic/ and ai/: the battle scene
calls Battle.ada_cast() and Battle.foe_act() and then plays back the events they report,
one narration beat at a time. Art is placeholder shapes for now (design doc 7.2: pixels last).

Two random generators exist on purpose: the battle's own (inside Battle, never touched here)
and game.vfx for screen shake, so visual effects can never change the outcome of a battle.

STATUS: title, intro dialogue, battle with narration, sounds, F1 overlay; result.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Callable

import pygame

from engine import render
from engine.audio import Audio, Silent
from engine.grimoire import Grimoire, draw_foe_book, wrap
from engine.textinput import QueryEditor, schema_tables, schema_words
from magic.battle import Battle
from magic.cast import SCRY_PER_TURN, CastReport, effect_word
from magic.db import DATA_DIR
from magic.guard import Miscast


def load_dialogue(path=DATA_DIR / "dialogue.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_cast_key(event) -> bool:
    return (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
            and bool(event.mod & pygame.KMOD_CTRL))


def is_confirm_key(event) -> bool:
    return event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                                          pygame.K_SPACE)


# ------------------------------------------------------------------ the scene machine

class Scene:
    def __init__(self, game: "Game"):
        self.game = game
        self.time = 0                     # ms since the scene started

    def enter(self) -> None: ...
    def exit(self) -> None: ...
    def handle(self, event: pygame.event.Event) -> None: ...

    def update(self, dt: int) -> None:
        self.time += dt

    def draw(self, canvas: pygame.Surface) -> None: ...


class Game:
    """Holds the current scene and what all scenes share. main.py runs the loop."""

    def __init__(self, canvas: pygame.Surface, seed: int, screen=None,
                 audio: Audio | None = None):
        self.canvas = canvas
        self.screen = screen              # optional: only used for screen shake
        self.audio = audio if audio is not None else Silent()
        self.seed = seed
        self.vfx = random.Random(seed)    # visual effects only, never the battle's rng
        self.dialogue = load_dialogue()
        self.debug = False
        self.running = True
        self.scene: Scene | None = None
        self.switch(TitleScene(self))

    def switch(self, scene: Scene) -> None:
        if self.scene:
            self.scene.exit()
        self.scene = scene
        scene.enter()

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
            self.debug = not self.debug
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
            self.audio.toggle_mute()
        else:
            self.scene.handle(event)

    def update(self, dt: int) -> None:
        self.scene.update(dt)

    def draw(self) -> None:
        if isinstance(self.canvas, render.Canvas):
            self.canvas.begin_frame()             # text is recorded per frame
        self.scene.draw(self.canvas)

    def shake(self, frames: int = 6) -> None:
        if self.screen is not None:
            self.screen.shake = frames


# ------------------------------------------------------------------ shared scenery

def draw_backdrop(canvas: pygame.Surface, ground_y: int = 60) -> None:
    """Night sky in bands, a few stars, the moon and the grass of the Tutorial Glade."""
    bands = [(0, render.INK), (12, render.NIGHT), (28, render.DUSK), (44, render.VIOLET)]
    for y, colour in bands:
        pygame.draw.rect(canvas, colour, (0, y, render.LOGICAL_W, ground_y - y))
    for i in range(24):                                    # stars on a fixed pattern
        canvas.set_at(((i * 53 + 17) % 320, (i * 29 + 5) % 40), render.LILAC)
    pygame.draw.circle(canvas, render.BUTTER, (292, 14), 7)
    pygame.draw.circle(canvas, render.NIGHT, (296, 12), 6)  # the moon's shadow side
    for x in range(0, render.LOGICAL_W, 8):                # a jagged tree line
        pygame.draw.polygon(canvas, render.FOREST,
                            [(x, ground_y), (x + 4, ground_y - 6 - (x // 8) % 3), (x + 8, ground_y)])
    pygame.draw.rect(canvas, render.FOREST, (0, ground_y, render.LOGICAL_W, 180 - ground_y))
    pygame.draw.rect(canvas, render.GRASS, (0, ground_y + 4, render.LOGICAL_W, 180 - ground_y))


def draw_slime(canvas: pygame.Surface, centre: tuple[int, int], t: int, flash: bool,
               exhausted: bool, fainted: bool) -> None:
    """Placeholder Asterisk Slime: a green dome with an asterisk heart (design doc fig. 11)."""
    cx, cy = centre
    body, edge = (render.WHITE, render.WHITE) if flash else (render.GRASS, render.FOREST)
    if fainted:
        pygame.draw.ellipse(canvas, edge, (cx - 20, cy + 10, 40, 8))
        return
    bob = (0, 1, 1, 0)[(t // 150) % 4] + (2 if exhausted else 0)   # idle: 4 frames x 150 ms
    top = cy - 16 + bob
    pygame.draw.ellipse(canvas, edge, (cx - 18, top, 36, 34))
    pygame.draw.rect(canvas, edge, (cx - 18, top + 17, 36, 16 - bob))
    pygame.draw.ellipse(canvas, body, (cx - 17, top + 1, 34, 32))
    pygame.draw.rect(canvas, body, (cx - 17, top + 17, 34, 15 - bob))
    if not flash:
        pygame.draw.rect(canvas, render.MINT, (cx - 10, top + 5, 3, 3))   # shine
        eye = 1 if exhausted else 3
        pygame.draw.rect(canvas, render.INK, (cx - 7, top + 13, 2, eye))
        pygame.draw.rect(canvas, render.INK, (cx + 5, top + 13, 2, eye))
        render.font().draw(canvas, "*", (cx - 3, top + 18), render.GOLD, scale=2)


def draw_ada_back(canvas: pygame.Surface, x: int, y: int, flash: bool) -> None:
    """Placeholder Ada seen from behind: hat, hair, robe (design doc 4.4)."""
    hat, brim, hair, robe = ((render.WHITE,) * 4 if flash else
                             (render.VIOLET, render.DUSK, render.LEATHER, render.NIGHT))
    pygame.draw.rect(canvas, robe, (x + 4, y + 30, 28, 12))
    pygame.draw.rect(canvas, hair, (x + 7, y + 16, 22, 18))
    pygame.draw.ellipse(canvas, brim, (x, y + 12, 36, 8))
    pygame.draw.polygon(canvas, hat, [(x + 22, y), (x + 8, y + 15), (x + 28, y + 15)])
    pygame.draw.rect(canvas, render.GOLD, (x + 9, y + 12, 18, 2))         # hat band


# ------------------------------------------------------------------ title

class TitleScene(Scene):
    def handle(self, event):
        if is_confirm_key(event):
            self.game.audio.play("confirm")
            self.game.switch(DialogueScene(self.game))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.running = False

    def draw(self, canvas):
        f = render.font()
        draw_backdrop(canvas, ground_y=120)
        title = "SQL WITCH"
        f.draw(canvas, title, ((320 - f.width(title, 4)) // 2, 40), render.BUTTER, scale=4,
               shadow=render.AMBER)
        sub = "a turn-based RPG where your queries are spells"
        f.draw(canvas, sub, ((320 - f.width(sub)) // 2, 74), render.LILAC)
        if (self.time // 500) % 2 == 0:
            prompt = "press ENTER"
            f.draw(canvas, prompt, ((320 - f.width(prompt)) // 2, 140), render.WHITE,
                   shadow=render.FOREST)
        f.draw(canvas, f"seed {self.game.seed}", (4, 172), render.FOREST)


# ------------------------------------------------------------------ dialogue

class DialogueScene(Scene):
    """Ada wakes up in Codd. ENTER finishes the line, then moves on; ESC skips the scene."""
    MS_PER_CHAR = 30

    def __init__(self, game):
        super().__init__(game)
        self.lines = game.dialogue["intro"]
        self.index = 0
        self.line_started = 0

    def _shown_chars(self) -> int:
        return (self.time - self.line_started) // self.MS_PER_CHAR

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.switch(BattleScene(self.game))
        elif is_confirm_key(event):
            text = self.lines[self.index]["text"]
            if self._shown_chars() < len(text):
                self.line_started = -10 ** 9            # finish the typewriter at once
            elif self.index + 1 < len(self.lines):
                self.index += 1
                self.line_started = self.time
            else:
                self.game.switch(BattleScene(self.game))

    def draw(self, canvas):
        f = render.font()
        draw_backdrop(canvas, ground_y=110)
        if self.index >= len(self.lines) - 1:             # the last line: the Slime appears
            draw_slime(canvas, (250, 96), self.time, False, False, False)
        line = self.lines[self.index]
        box = pygame.Rect(8, 128, 304, 44)
        render.panel(canvas, box)
        if line["speaker"]:
            tag = pygame.Rect(12, 121, f.width(line["speaker"]) + 8, 10)
            render.panel(canvas, tag, fill=render.VIOLET)
            f.draw(canvas, line["speaker"], (tag.x + 4, tag.y + 3), render.WHITE)
        text = line["text"][:max(0, self._shown_chars())]
        for i, row in enumerate(wrap(text, 74)[:4]):
            f.draw(canvas, row, (box.x + 4, box.y + 6 + i * render.LINE_H), render.INK)
        if self._shown_chars() >= len(line["text"]) and (self.time // 400) % 2 == 0:
            f.draw(canvas, "v", (box.right - 8, box.bottom - 9), render.VIOLET)


# ------------------------------------------------------------------ battle

@dataclass
class Beat:
    """One line of narration and, optionally, what it does to the picture when it starts."""
    text: str
    ms: int = 700
    effect: Callable[[], None] | None = None
    sounds: tuple[str, ...] = ()          # event names in assets/audio/sounds.json


@dataclass
class Popup:
    text: str
    pos: tuple[int, int]
    colour: tuple
    age: int = 0


SLIME_AT = (250, 50)
ADA_AT = (24, 58)


class BattleScene(Scene):
    WAIT_MS = 350                          # a short breath between turns

    def __init__(self, game):
        super().__init__(game)
        self.battle = Battle(seed=game.seed)
        conn = self.battle.conn
        self.editor = QueryEditor(names=schema_words(conn), tables=schema_tables(conn),
                                  unlocked=set(self.battle.state.ada.runes), visible_lines=6)
        self.grimoire = Grimoire(self.editor)
        self.beats: list[Beat] = []
        self.beat: Beat | None = None
        self.beat_left = 0
        self.popups: list[Popup] = []
        self.flash = {"ada": 0, "foe": 0}
        state = self.battle.state
        # What the bars show; narration effects move these, the true state catches up at rest.
        self.shown = {"ada": [state.ada.hp, state.ada.mp], "foe": [state.foe.hp, state.foe.mp]}
        self.bars = {side: [float(v) for v in values] for side, values in self.shown.items()}
        self.foe_sql: str | None = None
        self.foe_report: CastReport | None = None
        self.reasoning: dict = {}
        self.glow: tuple[str, int] | None = None
        self.idle = 0
        self.rounds_told = set()
        self.say(game.dialogue["battle_tip"], 2500)
        self.phase = "input" if self.battle.whose_turn == "ada" else "wait"

    def enter(self):
        pygame.key.start_text_input()
        self.game.audio.play_music("battle")

    def exit(self):
        pygame.key.stop_text_input()
        self.game.audio.stop_music()

    # ------------------------------------------------------------ narration

    def say(self, text: str, ms: int = 700, effect=None, *sounds: str) -> None:
        self.beats.append(Beat(text, ms, effect, sounds))

    def side_of(self, name: str) -> str:
        return "ada" if name == self.battle.state.ada.name else "foe"

    def _hit(self, side: str, damage: int, crit: bool):
        def effect():
            self.shown[side][0] = max(0, self.shown[side][0] - damage)
            self.flash[side] = 160
            x, y = (SLIME_AT[0], SLIME_AT[1] - 26) if side == "foe" else (ADA_AT[0] + 18, ADA_AT[1] - 6)
            self.popups.append(Popup(str(damage), (x, y), render.GOLD if crit else render.WHITE))
            if crit:
                self.game.shake()
        return effect

    def _set_shown(self, side: str, slot: int, value: int):
        def effect():
            self.shown[side][slot] = value
        return effect

    def _add_shown(self, side: str, slot: int, amount: int):
        def effect():
            self.shown[side][slot] += amount
        return effect

    def narrate(self, report: CastReport) -> None:
        """Turn the cast's events into beats, in the order they happened (design doc 7.3)."""
        margin = 0
        for event in report.events:
            kind = event[0]
            if kind == "cast":
                _, _, _, spell, target, dmg, crit, mult = event
                words = effect_word(mult)
                text = f"{spell}: {dmg}" + (" CRIT!" if crit else "") + (f" {words}!" if words else "")
                self.say(text, 650, self._hit(self.side_of(target), dmg, crit),
                         "crit" if crit else "hit", *(("hp_down",) if dmg else ()))
            elif kind in ("heal", "item"):
                side = self.side_of(event[3])
                amount = event[4] if kind == "heal" else event[5]
                slot = 1 if kind == "item" and event[4] == "mp" else 0
                self.say(f"{event[2]}: +{amount}", 600, self._add_shown(side, slot, amount),
                         "mp_up" if slot == 1 else "hp_up")
            elif kind == "ward":
                self.say(f"{event[2]}: ward {event[4]}", 600, None, "cast")
            elif kind == "fizzle":
                if event[3] == "overflow":
                    margin += 1
                elif event[3] == "duplicate":
                    self.say(f"{event[2]} again: it fizzles", 600, None, "fizzle")
                elif event[3] == "no_mana":
                    self.say(f"{event[2]}: no MP left", 450, None, "fizzle")
                else:
                    self.say(f"{event[2]}: none left", 450)
            elif kind == "mp":
                _, name, before, after = event
                if margin:
                    self.say(f"{margin} spells fizzle in the margin", 800, None, "fizzle")
                    margin = 0
                if before != after:
                    self.say(f"MP {before} -> {after}", 600,
                             self._set_shown(self.side_of(name), 1, after),
                             "mp_down" if after < before else "mp_up")
            elif kind == "exhausted":
                self.say(f"{event[1].split()[-1]} is EXHAUSTED!", 800)
            elif kind == "faint":
                self.say(f"{event[1]} faints!", 1000, None, "faint")
            elif kind == "scry":
                self.say("A free look." if not event[2] else "Nothing castable: turn spent.", 600)

    def _tell_round_end(self) -> None:
        end = self.battle.last_round
        if end and end.turn not in self.rounds_told:
            self.rounds_told.add(end.turn)
            self.say(f"Round {end.turn} ends: +{end.mp_gained['ada']} MP", 700, self._sync_shown,
                     *(("mp_up",) if end.mp_gained["ada"] else ()))

    def _sync_shown(self) -> None:
        state = self.battle.state
        self.shown = {"ada": [state.ada.hp, state.ada.mp], "foe": [state.foe.hp, state.foe.mp]}

    # ------------------------------------------------------------ turns

    def cast(self, sql: str) -> None:
        try:
            report = self.battle.ada_cast(sql)
        except Miscast as miscast:
            self.grimoire.show_miscast(str(miscast), self.time)
            self.game.audio.play("miscast")
            return
        self.game.audio.play("scry" if report.scry else "cast")
        looks = SCRY_PER_TURN - self.battle.state.scries_used
        self.grimoire.show_result(report, self.time, looks)
        self.narrate(report)
        self._tell_round_end()
        if report.ends_turn:
            self.phase, self.idle = "wait", 0

    def foe_turn(self) -> None:
        turn = self.battle.foe_act()
        self.foe_sql, self.foe_report, self.reasoning = turn.sql, turn.report, turn.reasoning
        self.say("The Slime casts!", 500, None, "scry" if turn.report.scry else "cast")
        self.narrate(turn.report)
        if turn.invitation:
            rune = turn.invitation

            def learn():
                self.editor.unlocked.add(rune)
                self.glow = (rune, self.time)
            self.say(f"{rune} glows in the Slime's book!", 1200, learn, "invitation")
            self.say(f"Ada copies the rune: {rune}", 1200)
        self._tell_round_end()

    # ------------------------------------------------------------ input and time

    def handle(self, event):
        if self.phase == "input":
            sql = self.editor.handle_event(event)
            if sql:
                self.cast(sql)
            return
        if is_cast_key(event):                      # Ctrl+Enter while waiting: fast-forward
            self.beat_left = 0
        elif self.phase != "end":
            self.editor.handle_event(event)         # typing ahead is fine, casting is not

    def update(self, dt):
        super().update(dt)
        self._update_beats(dt)
        self._update_visuals(dt)
        resting = self.beat is None and not self.beats
        if resting:
            self._sync_shown()
        if not resting or self.phase == "input":
            return
        self.idle += dt
        if self.idle < self.WAIT_MS:
            return
        self.idle = 0
        turn = self.battle.whose_turn
        if self.phase == "end":
            self.game.switch(ResultScene(self.game, self.battle))
        elif turn == "foe":
            self.foe_turn()
        elif turn == "ada":
            self.phase = "input"
        else:
            self.phase = "end"
            self.say("", 900)

    def _update_beats(self, dt: int) -> None:
        if self.beat is not None:
            self.beat_left -= dt
            if self.beat_left <= 0:
                self.beat = None
        if self.beat is None and self.beats:
            self.beat = self.beats.pop(0)
            self.beat_left = self.beat.ms
            if self.beat.effect:
                self.beat.effect()
            for sound in self.beat.sounds:
                self.game.audio.play(sound)

    def _update_visuals(self, dt: int) -> None:
        for side in ("ada", "foe"):
            self.flash[side] = max(0, self.flash[side] - dt)
            for slot in (0, 1):                      # bars glide at 60 points per second
                target, current = self.shown[side][slot], self.bars[side][slot]
                step = 60 * dt / 1000
                self.bars[side][slot] = target if abs(target - current) <= step else \
                    current + step * (1 if target > current else -1)
        for popup in self.popups:
            popup.age += dt
        self.popups = [p for p in self.popups if p.age < 800]

    # ------------------------------------------------------------ drawing

    def draw(self, canvas):
        f = render.font()
        state = self.battle.state
        draw_backdrop(canvas)
        pygame.draw.ellipse(canvas, render.MINT, (SLIME_AT[0] - 28, SLIME_AT[1] + 12, 56, 10))
        draw_slime(canvas, SLIME_AT, self.time, self.flash["foe"] > 0 and (self.time // 40) % 2 == 0,
                   state.foe.exhausted, self.bars["foe"][0] <= 0)
        draw_ada_back(canvas, *ADA_AT, self.flash["ada"] > 0 and (self.time // 40) % 2 == 0)

        self._draw_foe_panel(canvas)
        glow_word = self.glow[0] if self.glow and self.time - self.glow[1] < 4000 else None
        draw_foe_book(canvas, state.foe.name, self.foe_sql, self.foe_report, glow_word, self.time)
        self._draw_ada_panel(canvas)

        if self.beat is not None and self.beat.text:
            box = pygame.Rect(64, 80, 128, 17)
            render.panel(canvas, box)
            for i, line in enumerate(wrap(self.beat.text, 30)[:2]):
                f.draw(canvas, line, (box.x + 4, box.y + 3 + i * render.LINE_H), render.INK)
        for p in self.popups:
            f.draw(canvas, p.text, (p.pos[0] - f.width(p.text) // 2, p.pos[1] - p.age // 60),
                   p.colour, shadow=render.INK)

        self.grimoire.draw(canvas, self.time, focused=self.phase == "input")
        if self.game.debug:
            self._draw_debug(canvas)

    def _draw_foe_panel(self, canvas):
        f, foe = render.font(), self.battle.state.foe
        box = pygame.Rect(4, 3, 120, 20)
        render.panel(canvas, box)
        f.draw(canvas, foe.name.upper(), (box.x + 4, box.y + 3), render.INK)
        f.draw(canvas, "Lv1", (box.right - 16, box.y + 3), render.SLATE)
        f.draw(canvas, "HP", (box.x + 4, box.y + 11), render.AMBER)
        render.meter(canvas, pygame.Rect(box.x + 14, box.y + 11, 100, 5),
                     round(self.bars["foe"][0]), foe.max_hp, render.GOLD)
        if foe.exhausted:
            f.draw(canvas, "EXHAUSTED", (box.right + 4, box.y + 3), render.RED, shadow=render.INK)

    def _draw_ada_panel(self, canvas):
        f, ada = render.font(), self.battle.state.ada
        box = pygame.Rect(196, 70, 120, 27)
        render.panel(canvas, box)
        hp, mp = round(self.bars["ada"][0]), round(self.bars["ada"][1])
        f.draw(canvas, "ADA", (box.x + 4, box.y + 3), render.INK)
        f.draw(canvas, f"{hp}/{ada.max_hp}", (box.x + 52, box.y + 3), render.FOREST)
        f.draw(canvas, "Lv1", (box.right - 16, box.y + 3), render.SLATE)
        f.draw(canvas, "HP", (box.x + 4, box.y + 11), render.AMBER)
        render.meter(canvas, pygame.Rect(box.x + 14, box.y + 11, 100, 5), hp, ada.max_hp,
                     render.GRASS)
        f.draw(canvas, "MP", (box.x + 4, box.y + 18), render.BLUE)
        render.meter(canvas, pygame.Rect(box.x + 14, box.y + 18, 70, 5), mp, ada.max_mp,
                     render.SKY)
        f.draw(canvas, f"{mp}/{ada.max_mp}", (box.x + 88, box.y + 18), render.NAVY)
        runes = "RUNES: " + (", ".join(sorted(ada.runes)) or "none")
        f.draw(canvas, runes, (box.x, box.y - 8), render.GOLD, shadow=render.INK)
        if ada.exhausted:
            f.draw(canvas, "EXHAUSTED", (box.right - f.width("EXHAUSTED"), box.y - 8),
                   render.RED, shadow=render.INK)

    def _draw_debug(self, canvas):
        """F1: what the brain was thinking, straight from Brain.explain()."""
        f = render.font()
        battle = self.battle
        lines = [f"DEBUG (F1)   seed {battle.seed}   round {battle.state.turn}   "
                 f"turn: {battle.whose_turn}   looks used: {battle.state.scries_used}"]
        if self.reasoning:
            for key, value in self.reasoning.items():
                lines.extend(wrap(f"{key}: {value}", 76))
        else:
            lines.append("The Slime has not decided anything yet.")
        lines.append(f"Slime book: {len(battle.state.foe_book)} queries")
        render.cover(canvas, pygame.Rect(4, 4, 312, 8 + len(lines) * render.LINE_H),
                     (*render.INK, 235))
        for i, line in enumerate(lines):
            f.draw(canvas, line, (8, 8 + i * render.LINE_H),
                   render.GOLD if i == 0 else render.MINT)


# ------------------------------------------------------------------ result

class ResultScene(Scene):
    def __init__(self, game, battle: Battle):
        super().__init__(game)
        self.battle = battle
        self.won = battle.winner == "ada"
        conn = battle.conn
        self.queries, self.casts = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(rows_cast), 0) FROM query_log WHERE caster = ?",
            (battle.state.ada.name,)).fetchone()
        # The Codex records the guardian's own query as the example for the rune (design doc 3.6).
        self.codex = next((sql for sql in battle.state.foe_book if "LIMIT" in sql), None)

    def enter(self):
        self.game.audio.play("victory" if self.won else "defeat")

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.running = False
        elif is_confirm_key(event):
            self.game.seed += 1                      # a new, still reproducible battle
            self.game.switch(BattleScene(self.game))

    def draw(self, canvas):
        f = render.font()
        draw_backdrop(canvas, ground_y=150)
        headline = "VICTORY" if self.won else "DEFEAT"
        f.draw(canvas, headline, ((320 - f.width(headline, 4)) // 2, 16),
               render.BUTTER if self.won else render.RED, scale=4, shadow=render.INK)
        lines = self.game.dialogue["victory" if self.won else "defeat"]
        y = 52
        for line in lines:
            f.draw(canvas, line, ((320 - f.width(line)) // 2, y), render.WHITE)
            y += 9
        state = self.battle.state
        stats = [f"rounds {state.turn}   queries {self.queries}   spells cast {self.casts}",
                 f"HP left {state.ada.hp}/{state.ada.max_hp}   seed {self.battle.seed}"]
        y += 6
        for line in stats:
            f.draw(canvas, line, ((320 - f.width(line)) // 2, y), render.LILAC)
            y += 9
        if self.codex and "LIMIT" in state.ada.runes:
            y += 6
            box = pygame.Rect(30, y, 260, 30)
            render.panel(canvas, box)
            f.draw(canvas, "CODEX - LIMIT, as the Slime cast it:", (box.x + 4, box.y + 3),
                   render.VIOLET)
            for i, line in enumerate(wrap(self.codex, 62)[:2]):
                f.draw(canvas, line, (box.x + 4, box.y + 12 + i * render.LINE_H), render.INK)
        prompt = "ENTER play again    ESC quit"
        if (self.time // 500) % 2 == 0:
            f.draw(canvas, prompt, ((320 - f.width(prompt)) // 2, 166), render.WHITE,
                   shadow=render.FOREST)
