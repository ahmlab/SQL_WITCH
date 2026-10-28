"""The Grimoire: the query on the left page, its result on the right (design doc 3.3, 6.4).

The result table is drawn whole, through a clip rectangle the size of the page, so it can be
taller and wider than the page. The clip is what cuts row five in half and hides the
columns past the right edge; nothing here decides what is readable, magic/cast.py does.
When the result has more rows than PAGE_ROWS, ink drips off the bottom of the page.

Also here: the Slime's book (the foe's last query, with its signature rune glowing when the
Invitation fires).

STATUS: step 6 done - pages, clipped table, ink-in rows, drips, status line, foe book.
"""

from __future__ import annotations

import pygame

from engine import render
from engine.textinput import QueryEditor, colour_styles, STYLE_COLOURS
from magic.cast import PAGE_ROWS, CastReport, cell_text, column_widths

# Layout in logical pixels (design doc 6.4: the right page is 146 x 64 at (166, 106)).
BOOK = pygame.Rect(0, 100, 320, 80)
LEFT_PAGE = pygame.Rect(8, 106, 146, 64)
RIGHT_PAGE = pygame.Rect(166, 106, 146, 64)
TABLE_TOP = 8                    # the "RESULT" label sits above the table on the right page
ROW_H = 11                       # with TEXT_DY, row five's letters are cut in half by the clip
TEXT_DY = 1                      # text offset inside a row
INK_MS = 40                      # one result row inks onto the page every 40 ms (design doc 7.3)
GAP = render.ADVANCE             # one character between columns, as in magic.cast


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap to `width` characters; long words are cut."""
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


def column_x(columns: list[str], rows: list[tuple]) -> list[int]:
    """Left edge of every column in pixels: the same character widths magic.cast uses."""
    xs, x = [], 0
    for width in column_widths(columns, rows):
        xs.append(x)
        x += width * render.ADVANCE + GAP
    return xs


def draw_table(surface: pygame.Surface, report: CastReport, rows_shown: int,
               topleft: tuple[int, int]) -> None:
    """Draw the whole result table from topleft. It may be bigger than the page: the caller
    sets the clip, and the clip is what cuts row five and the columns past the edge."""
    f = render.font()
    columns, rows = report.columns, report.rows
    widths = column_widths(columns, rows)
    xs = column_x(columns, rows)
    total_w = (xs[-1] + widths[-1] * render.ADVANCE) if xs else 1
    x0, y0 = topleft
    for name, x in zip(columns, xs):
        f.draw(surface, name, (x0 + x, y0), render.LEATHER)
    pygame.draw.line(surface, render.LEATHER, (x0, y0 + render.GLYPH_H + 1),
                     (x0 + total_w, y0 + render.GLYPH_H + 1))
    for i, row in enumerate(rows[:min(rows_shown, PAGE_ROWS + 1)]):   # nobody sees past row 5
        y = y0 + TABLE_TOP + i * ROW_H
        for value, x in zip(row, xs):
            f.draw(surface, cell_text(value), (x0 + x, y + TEXT_DY), render.INK)
        for dot in range(0, total_w, 3):                        # dotted row separator
            surface.set_at((x0 + dot, y + ROW_H - 2), render.SAND)


class Grimoire:
    """Owns the left-page editor and the right-page result. Scenes call show_*() and draw()."""

    def __init__(self, editor: QueryEditor):
        self.editor = editor
        self.report: CastReport | None = None
        self.miscast: str | None = None
        self.shown_at = 0
        self.looks_left = 3

    def show_result(self, report: CastReport, now: int, looks_left: int) -> None:
        self.report, self.miscast, self.shown_at = report, None, now
        self.looks_left = looks_left

    def show_miscast(self, message: str, now: int) -> None:
        self.report, self.miscast, self.shown_at = None, message, now

    # ------------------------------------------------------------ drawing

    def draw(self, surface: pygame.Surface, now: int, focused: bool) -> None:
        f = render.font()
        # The book: leather cover, two cream pages and a spine.
        pygame.draw.rect(surface, render.BARK, BOOK)
        pygame.draw.rect(surface, render.LEATHER, BOOK.inflate(-4, -4))
        for page in (LEFT_PAGE, RIGHT_PAGE):
            pygame.draw.rect(surface, render.CREAM, page.inflate(6, 6))
        pygame.draw.line(surface, render.SAND, (160, 104), (160, 172))

        # Left page: the query being written.
        f.draw(surface, "YOUR QUERY", (LEFT_PAGE.x, LEFT_PAGE.y), render.VIOLET)
        looks = f"looks {self.looks_left}"
        f.draw(surface, looks, (LEFT_PAGE.right - f.width(looks), LEFT_PAGE.y), render.SAND)
        self.editor.draw(surface, (LEFT_PAGE.x, LEFT_PAGE.y + 9), now, focused)
        self._draw_status(surface)

        # Right page: the result, cut by the page.
        f.draw(surface, "RESULT", (RIGHT_PAGE.x, RIGHT_PAGE.y), render.VIOLET)
        if self.miscast:
            self._draw_miscast(surface)
        elif self.report:
            self._draw_result(surface, now)

        f.draw(surface, "CTRL+ENTER cast  TAB complete  F1 debug", (8, 173), render.BUTTER)

    def _draw_status(self, surface: pygame.Surface) -> None:
        box = pygame.Rect(LEFT_PAGE.x, LEFT_PAGE.bottom - 9, LEFT_PAGE.width, 9)
        if self.report is None:
            return
        report = self.report
        if report.scry and not report.ends_turn:
            text, border = f"{len(report.rows)} rows | a free look | MP {report.mp_after}", \
                render.TEAL
        else:
            text = report.status_line()
            border = render.RED if report.overflow else render.INK
        # Squeeze the spaces out before anything gets cut off the page.
        f = render.font()
        for squeeze in ((" -> ", "->"), (" | ", "|")):
            if f.width(text) > box.width - 4:
                text = text.replace(*squeeze)
        pygame.draw.rect(surface, border, box, 1)
        f.draw(surface, text, (box.x + 2, box.y + 2), border)

    def _draw_miscast(self, surface: pygame.Surface) -> None:
        f = render.font()
        f.draw(surface, "*poof*", (RIGHT_PAGE.x, RIGHT_PAGE.y + 10), render.GREY)
        for i, line in enumerate(wrap(self.miscast, 36)[:6]):
            f.draw(surface, line, (RIGHT_PAGE.x, RIGHT_PAGE.y + 19 + i * render.LINE_H),
                   render.WINE)

    def _draw_result(self, surface: pygame.Surface, now: int) -> None:
        report = self.report
        if not report.rows:
            render.font().draw(surface, "(the page stays blank)",
                               (RIGHT_PAGE.x, RIGHT_PAGE.y + 12), render.GREY)
            return
        rows_shown = 1 + (now - self.shown_at) // INK_MS            # ink in, row by row
        clip = pygame.Rect(RIGHT_PAGE.x, RIGHT_PAGE.y + TABLE_TOP,
                           RIGHT_PAGE.width, RIGHT_PAGE.height - TABLE_TOP)
        surface.set_clip(clip)
        draw_table(surface, report, rows_shown, clip.topleft)      # row 5 is cut in half here
        surface.set_clip(None)

        # A gold star in the spine marks every row that cast (design doc 4.4).
        cast_rows = {c.row for c in report.casts}
        for row in range(min(PAGE_ROWS, rows_shown, len(report.rows))):
            if row in cast_rows:
                y = clip.y + TABLE_TOP + row * ROW_H + TEXT_DY
                render.font().draw(surface, "*", (RIGHT_PAGE.x - 5, y), render.GOLD)

        if len(report.rows) > PAGE_ROWS and rows_shown > PAGE_ROWS:
            self._draw_drips(surface, now - self.shown_at - PAGE_ROWS * INK_MS)

    def _draw_drips(self, surface: pygame.Surface, age_ms: int) -> None:
        """Grey ink keeps running off the bottom edge: the table did not stop (design doc 3.3)."""
        report = self.report
        xs = column_x(report.columns, report.rows)
        bottom = RIGHT_PAGE.bottom + 3
        for i, x in enumerate(xs):
            if x > RIGHT_PAGE.width - 4:
                break
            longest = 3 + (i * 5) % 5                                  # fixed, not random
            length = min(longest, max(0, age_ms // 120 - i))
            if length <= 0:
                continue
            px = RIGHT_PAGE.x + x + 2
            pygame.draw.line(surface, render.GREY, (px, bottom), (px, bottom + length))
            surface.set_at((px - 1, bottom + length), render.GREY)
            surface.set_at((px + 1, bottom + length), render.GREY)


# ------------------------------------------------------------------ the foe's book

FOE_BOOK = pygame.Rect(4, 25, 152, 33)


def foe_summary(report: CastReport | None) -> str:
    if report is None:
        return ""
    if not report.casts:
        return f"{len(report.rows)} rows - nothing castable."
    text = f"{len(report.rows)} rows"
    if report.overflow:
        text += f" - {report.overflow} fell off its page"
    return text + f". MP {report.mp_after}" + ("!" if report.mp_after == 0 else ".")


def draw_foe_book(surface: pygame.Surface, foe_name: str, sql: str | None,
                  report: CastReport | None, glow_word: str | None, now: int) -> None:
    """The foe's last query, printed in its book. The signature rune glows (the Invitation)."""
    f = render.font()
    render.panel(surface, FOE_BOOK)
    title = f"{foe_name.split()[-1].upper()} CAST:"
    f.draw(surface, title, (FOE_BOOK.x + 4, FOE_BOOK.y + 3), render.RED)
    if not sql:
        f.draw(surface, "(waiting)", (FOE_BOOK.x + 4, FOE_BOOK.y + 11), render.GREY)
        return
    lines = wrap(sql, 36)[:2]
    for n, line in enumerate(lines):
        x0, y0 = FOE_BOOK.x + 4, FOE_BOOK.y + 11 + n * render.LINE_H
        styles = colour_styles(line, set(), set())
        if glow_word and glow_word in line:
            start = line.index(glow_word)
            pulse = render.BUTTER if (now // 250) % 2 == 0 else render.GOLD
            glow = pygame.Rect(x0 + start * render.ADVANCE - 1, y0 - 1,
                               len(glow_word) * render.ADVANCE + 1, render.GLYPH_H + 1)
            pygame.draw.rect(surface, pulse, glow)
        render.draw_coloured(surface, line, [STYLE_COLOURS[st] for st in styles], (x0, y0))
    f.draw(surface, foe_summary(report)[:36], (FOE_BOOK.x + 4, FOE_BOOK.y + 25), render.WINE)
