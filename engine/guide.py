"""The spell guide (F3): how to write a query, how to read a table, and what to try now.

For players who have never written SQL. Four pages: the basics and the casting rules, the
tables of this world with a real result explained, ready-made queries (marked as a free LOOK
or a CAST, and only those Ada has the runes for) that ENTER writes onto the page, and the runes.
Text lives in data/guide.json, so it can be edited without touching code.

Everything is drawn on the text layer (render.cover + text), so the guide sits above the
battle, including the battle's own text.

STATUS: four pages, keyboard and mouse, examples filtered by Ada's runes.
"""

from __future__ import annotations

import json

import pygame

from engine import render
from engine.grimoire import wrap
from engine.textinput import STYLE_COLOURS, colour_styles, locked_words
from magic.db import DATA_DIR

PAGES = ["BASICS", "TABLES", "TRY THESE", "RUNES"]
BOX = pygame.Rect(8, 6, 304, 168)
COLS = 73                                     # characters per line inside the box
VISIBLE_EXAMPLES = 8


def load_guide(path=DATA_DIR / "guide.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Guide:
    def __init__(self, conn, runes: set[str], content: dict | None = None):
        self.conn = conn                      # the battle database: tables and a real row
        self.runes = runes                    # Ada's runes (the live set: it grows in battle)
        self.content = content or load_guide()
        self.open = False
        self.page = 0
        self.choice = 0
        self.opened_once = False

    # ------------------------------------------------------------ what is shown

    def examples(self) -> list[dict]:
        """Every example, each marked whether Ada can cast it with her runes right now."""
        return [dict(e, ready=set(e["needs"]) <= self.runes) for e in self.content["examples"]]

    def toggle(self) -> None:
        self.open = not self.open
        self.opened_once = self.opened_once or self.open

    # ------------------------------------------------------------ input

    def handle(self, event) -> str | None:
        """Feed a key while the guide is open. Returns a query to write on the page, if any."""
        if event.type != pygame.KEYDOWN:
            return None
        key = event.key
        if key in (pygame.K_ESCAPE, pygame.K_F3):
            self.open = False
        elif key == pygame.K_RIGHT:
            self.page = (self.page + 1) % len(PAGES)
        elif key == pygame.K_LEFT:
            self.page = (self.page - 1) % len(PAGES)
        elif pygame.K_1 <= key <= pygame.K_4:
            self.page = key - pygame.K_1
        elif PAGES[self.page] == "TRY THESE":
            examples = self.examples()
            if key == pygame.K_DOWN:
                self.choice = min(len(examples) - 1, self.choice + 1)
            elif key == pygame.K_UP:
                self.choice = max(0, self.choice - 1)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and examples[self.choice]["ready"]:
                self.open = False
                return examples[self.choice]["sql"]
        return None

    def click(self, x: int, y: int) -> None:
        """A click on a tab opens that page."""
        for i, rect in enumerate(self._tab_rects()):
            if rect.collidepoint(x, y):
                self.page = i

    # ------------------------------------------------------------ drawing

    def _tab_rects(self) -> list[pygame.Rect]:
        rects, x = [], BOX.x + 4
        for name in PAGES:
            w = render.font().width(f"{PAGES.index(name) + 1} {name}") + 8
            rects.append(pygame.Rect(x, BOX.y + 3, w, 10))
            x += w + 3
        return rects

    def draw(self, canvas: pygame.Surface, now: int) -> None:
        if not self.open:
            return
        f = render.font()
        render.cover(canvas, canvas.get_rect(), (*render.INK, 170))     # dim the battle
        render.cover(canvas, BOX, (*render.INK, 255))
        render.cover(canvas, BOX.inflate(-2, -2), (*render.CREAM, 255))
        for i, rect in enumerate(self._tab_rects()):
            if i == self.page:
                render.cover(canvas, rect, (*render.VIOLET, 255))
            f.draw(canvas, f"{i + 1} {PAGES[i]}", (rect.x + 4, rect.y + 2),
                   render.WHITE if i == self.page else render.VIOLET)
        f.draw(canvas, "SPELL GUIDE", (BOX.right - f.width("SPELL GUIDE") - 5, BOX.y + 5),
               render.SAND)
        top = BOX.y + 18
        getattr(self, "_page_" + PAGES[self.page].lower().replace(" ", "_"))(canvas, top, now)
        hint = "<- -> pages   UP/DOWN choose   ENTER write it on the page   F3/ESC close"
        f.draw(canvas, hint, (BOX.x + 5, BOX.bottom - 9), render.SLATE)

    def _text(self, canvas, lines, top, colour=render.INK) -> int:
        f, y = render.font(), top
        for line in lines:
            heading = line.isupper() and line.strip()
            indent = len(line) - len(line.lstrip())
            for part in wrap(line, COLS - indent) or [""]:   # never cut a line off the box
                f.draw(canvas, " " * indent + part, (BOX.x + 5, y),
                       render.VIOLET if heading else colour)
                y += render.LINE_H
        return y

    def _page_basics(self, canvas, top, now) -> None:
        self._text(canvas, self.content["basics"], top)

    def _page_tables(self, canvas, top, now) -> None:
        f = render.font()
        y = self._text(canvas, [self.content["tables_intro"], ""], top)
        for table, meaning in self.content["tables"].items():
            f.draw(canvas, table, (BOX.x + 5, y), render.TEAL)
            f.draw(canvas, meaning[:COLS - 12], (BOX.x + 5 + 12 * render.ADVANCE, y), render.INK)
            y += render.LINE_H
        y += 4
        y = self._text(canvas, self.content["reading"], y)
        self._sample(canvas, y + 3)

    def _sample(self, canvas, y) -> None:
        """A real row from this battle, printed like the right page prints it."""
        f = render.font()
        cur = self.conn.execute("SELECT name, hp, element, weakness FROM enemies")
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        table = [columns] + [["NULL" if v is None else str(v) for v in row] for row in rows]
        widths = [max(len(r[i]) for r in table) for i in range(len(columns))]
        for n, row in enumerate(table):
            x = BOX.x + 20
            for i, cell in enumerate(row):
                colour = render.LEATHER if n == 0 else (render.RED if i == 3 else render.INK)
                f.draw(canvas, cell, (x, y), colour)
                x += (widths[i] + 1) * render.ADVANCE
            y += render.LINE_H

    def _page_try_these(self, canvas, top, now) -> None:
        f = render.font()
        examples = self.examples()
        first = max(0, min(self.choice - VISIBLE_EXAMPLES // 2, len(examples) - VISIBLE_EXAMPLES))
        locked = locked_words(self.runes)
        y = top
        for i in range(first, min(len(examples), first + VISIBLE_EXAMPLES)):
            e = examples[i]
            row = pygame.Rect(BOX.x + 3, y - 1, BOX.width - 6, 2 * render.LINE_H + 1)
            if i == self.choice:
                render.cover(canvas, row, (*render.BUTTER, 255))
            tag = "LOOK" if e["kind"] == "look" else "CAST"
            tag_colour = render.TEAL if e["kind"] == "look" else render.RED
            if not e["ready"]:
                tag_colour = render.GREY
            f.draw(canvas, tag, (BOX.x + 5, y), tag_colour)
            styles = colour_styles(e["sql"], locked, set(self.content["tables"]))
            colours = [STYLE_COLOURS[s] if e["ready"] else render.GREY for s in styles]
            render.draw_coloured(canvas, e["sql"][:COLS - 6], colours, (BOX.x + 5 + 5 * render.ADVANCE, y))
            say = e["say"] if e["ready"] else f"learn {', '.join(sorted(set(e['needs']) - self.runes))} first"
            f.draw(canvas, say[:COLS - 6], (BOX.x + 5 + 5 * render.ADVANCE, y + render.LINE_H),
                   render.SLATE)
            y += 2 * render.LINE_H + 2
        if first + VISIBLE_EXAMPLES < len(examples):
            f.draw(canvas, "v more", (BOX.right - 30, BOX.bottom - 18), render.SAND)

    def _page_runes(self, canvas, top, now) -> None:
        f, y = render.font(), top
        y = self._text(canvas, ["Runes are SQL keywords. You learn each one from the guardian",
                                "who uses it: watch its book, then copy it.", ""], y)
        for r in self.content["runes"]:
            known = r["rune"] in self.runes
            f.draw(canvas, r["rune"], (BOX.x + 5, y), render.GOLD if known else render.GREY)
            f.draw(canvas, "known" if known else f"from {r['from']}",
                   (BOX.x + 5 + 10 * render.ADVANCE, y), render.FOREST if known else render.SLATE)
            f.draw(canvas, r["does"][:COLS - 4], (BOX.x + 5 + 4 * render.ADVANCE, y + render.LINE_H),
                   render.INK if known else render.GREY)
            y += 2 * render.LINE_H + 3
