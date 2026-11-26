"""Dialogue on screen: text boxes, the typewriter, inline effects, portraits and the log.

Draws what story/ decided. A DialogueBox shows one line:
- wrapped with the real font's measurements (wrap_text): Latin and other spaced scripts break
  between words (no hyphenation); CJK breaks between any two characters, but never puts
  closing punctuation at the start of a line or opening punctuation at its end;
- revealed by story.pacing.Typewriter, character by character;
- with inline effects per character: {wave} rises and falls, {shake} trembles, {color gold}
  colours, {rune WHERE} glows behind the word;
- if a line has more rows than its box (a long translation), the box scrolls inside itself as
  the typewriter goes, so text never spills out of the box;
- styled per kind of speaker (data/pacing.json: narrator, Ada, Grimoire, guardian, companion,
  letter), with the speaker's name on a tag and a portrait frame when a [portrait] direction
  asks for one (assets/portraits/<who>_<emotion>.png when it exists, a placeholder until then).

Never decides what is said: story/ does.

STATUS: wrapping (Latin and CJK), typewriter drawing, effects, scrolling, styles, portraits, log.
"""

from __future__ import annotations

import math
from pathlib import Path

import pygame

from engine import gfx

from engine import render
from i18n.width import text_cells, wrap
from story.pacing import style_of
from story.scenes import speaker_name
from story.script import Token

PORTRAITS = Path(__file__).resolve().parent.parent / "assets" / "portraits"
# Portraits built at run time, by who: the protagonist's comes from their layered look
# (engine/animation.py), registered by the game. Everyone else uses assets/portraits/.
portraits: dict = {}


def measure(text: str) -> int:
    """Width of a text in canvas pixels with the game's font (CJK takes two cells)."""
    return max(0, text_cells(text) * render.ADVANCE - 1)


def wrap_text(text: str, width: int) -> list[str]:
    """Lines that fit `width` pixels: i18n.width.wrap, in cells of the text grid."""
    return wrap(text, (width + 1) // render.ADVANCE)


def colour(name: str | None, default: tuple) -> tuple:
    return getattr(render, name.upper(), default) if name else default


class DialogueBox:
    """One text box. draw() shows `shown` characters of a line's tokens."""

    def __init__(self, rect: pygame.Rect, rows: int, opaque: bool = False):
        self.rect = pygame.Rect(rect)
        self.rows = rows
        # opaque: over a scene with text on the text layer (the battle), the box must hide it,
        # which only render.cover does.
        self.opaque = opaque

    def _panel(self, canvas, rect, fill, border) -> None:
        if self.opaque:
            render.cover(canvas, rect, (*border, 255))
            render.cover(canvas, rect.inflate(-2, -2), (*fill, 255))
        else:
            render.panel(canvas, rect, fill=fill, border=border)

    def layout(self, tokens: list[Token]) -> list[list[tuple[str, Token]]]:
        """The line's characters, wrapped into rows, each with its style."""
        text = "".join(t.text for t in tokens if t.kind == "text")
        styled = [(c, t) for t in tokens if t.kind == "text" for c in t.text]
        rows, k = [], 0
        for row in wrap_text(text, self.rect.width - 8):
            out = []
            for char in row:                          # match the row to the styled characters
                while k < len(styled) and styled[k][0] != char:
                    k += 1                            # spaces and newlines eaten by the wrap
                if k < len(styled):
                    out.append(styled[k])
                    k += 1
            rows.append(out)
        return rows

    def overflows(self, tokens: list[Token]) -> bool:
        return len(self.layout(tokens)) > self.rows

    def draw(self, canvas: pygame.Surface, speaker: str, tokens: list[Token], shown: int,
             now: int, portrait: tuple | None = None) -> pygame.Rect:
        f = render.font()
        style = style_of(speaker)
        label = speaker_name(speaker)
        box = self.rect
        self._panel(canvas, box, colour(style.get("fill"), render.CREAM),
                    colour(style.get("border"), render.INK))
        if label and style.get("tag"):
            tag = pygame.Rect(box.x + 4, box.y - 7, f.width(label) + 8, 10)
            self._panel(canvas, tag, colour(style["tag"], render.LAVENDER), render.INK)
            f.draw(canvas, label, (tag.x + 4, tag.y + 3), render.WHITE)
        if portrait:
            self._portrait(canvas, portrait)
        rows = self.layout(tokens)
        # Which rows to show: the ones around the typewriter, so a long line scrolls.
        upto, count = 0, 0
        for r, row in enumerate(rows):
            count += len(row)
            upto = r
            if count >= shown:
                break
        first = max(0, upto - self.rows + 1)
        drawn = 0
        for r, row in enumerate(rows):
            if r < first:
                drawn += len(row)
                continue
            if r >= first + self.rows:
                break
            x = box.x + 4
            y = box.y + 5 + (r - first) * render.LINE_H
            for i, (char, token) in enumerate(row):
                if drawn >= shown:
                    return box
                drawn += 1
                dx = dy = 0
                if token.wave:
                    dy = round(math.sin(now / 130 + (x + i) * 0.5))
                if token.shake:
                    dx = ((now // 45 + i * 7) % 3) - 1
                    dy += ((now // 60 + i * 5) % 3) - 1
                if token.rune:
                    gfx.rect(canvas, render.BUTTER,
                                     (x - 1, y - 1, measure(char) + 2, render.GLYPH_H + 1))
                ink = colour(token.color, render.INK)
                f.draw(canvas, char, (x + dx, y + dy), ink)
                x += measure(char) + 1
        return box

    def _portrait(self, canvas: pygame.Surface, portrait: tuple) -> None:
        who, emotion = (portrait + ("neutral",))[:2]
        frame = pygame.Rect(self.rect.right - 36, self.rect.y - 34, 32, 32)
        if who in portraits:
            canvas.blit(portraits[who](emotion), frame)
            return
        path = PORTRAITS / f"{who}_{emotion}.png"
        if path.exists():
            canvas.blit(pygame.image.load(str(path)), frame)
            return
        render.panel(canvas, frame, fill=render.PARCHMENT)    # until the art exists
        f = render.font()
        f.draw(canvas, who[:1].upper(), (frame.centerx - 2, frame.y + 8), render.VIOLET)
        f.draw(canvas, emotion[:7], (frame.x + 3, frame.bottom - 9), render.SLATE)


def draw_log(canvas: pygame.Surface, entries: list[tuple[str, str]], hint: str) -> None:
    """The dialogue log: the last lines said, newest at the bottom."""
    f = render.font()
    box = pygame.Rect(8, 6, 304, 168)
    render.cover(canvas, box, (*render.INK, 245))
    y = box.bottom - 18
    for speaker, text in reversed(entries):
        said = f"{speaker_name(speaker)}: {text}" if speaker else text
        rows = wrap_text(said, box.width - 12)
        for row in reversed(rows):
            if y < box.y + 4:
                break
            f.draw(canvas, row, (box.x + 6, y), render.LILAC if speaker else render.GREY)
            y -= render.LINE_H
        y -= 3
    f.draw(canvas, hint, (box.x + 6, box.bottom - 9), render.GOLD)
