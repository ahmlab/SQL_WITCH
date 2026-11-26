"""The font service: which glyph draws each character, in every language (plan D9, prompt 04).

The text layer (engine/render.py) asks this module for every character it draws:
1. the game's own 5x7 pixel letters (ASCII) when they exist;
2. for accented Latin letters (all EU languages: á è ô ñ ç ß ł ő ű ą ę ș ț ā ė į ų ž ħ ġ ċ...),
   the base letter with its accent drawn in the same pixel style: the accent comes from the
   Unicode decomposition (é = e + acute), so every combination works, and the few letters that
   do not decompose (ß ł ø æ œ đ ħ, quotes, ¿ ¡ « » … € –) are drawn by hand below;
3. anything else (Chinese, Greek, Cyrillic) from GNU Unifont, a bitmap font with every
   character of both Simplified and Traditional Chinese, at a whole-number pixel size so it
   stays crisp on the 2x text layer. A Chinese character takes two cells of the text grid.
Text that mixes scripts is drawn character by character, so each run gets its own font.

Licences: the pixel letters are the game's own; GNU Unifont is under the SIL Open Font
Licence 1.1 (or GPL 2+ with the font exception), see CREDITS.md.

STATUS: 5x7 letters, composed accents, hand-drawn extras, Unifont fallback, coverage check.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import pygame

from engine import gfx

from i18n.width import cells

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
UNIFONT = FONTS / "unifont.otf"
# HD text (a 1280x720 canvas): JetBrains Mono, monospaced, sized to the 4-pixel grid's cell,
# for every Latin, Greek and Cyrillic character; Chinese stays with Unifont.
HD_FONT = {False: FONTS / "JetBrainsMono-SemiBold.ttf", True: FONTS / "JetBrainsMono-ExtraBold.ttf"}
HD_FROM_K = 3                     # from this many real pixels per logical pixel, text is HD
UNIFONT_PX = 16

# Accents above, as rows 5 dots wide, and below (cedilla, ogonek, comma).
ABOVE = {
    "́": ["...#.", "..#.."],          # acute
    "̀": [".#...", "..#.."],          # grave
    "̂": ["..#..", ".#.#."],          # circumflex
    "̌": [".#.#.", "..#.."],          # caron
    "̈": [".#.#."],                   # diaeresis
    "̃": [".##.#", "#..#."],          # tilde
    "̊": ["..#..", ".#.#.", "..#.."],  # ring
    "̇": ["..#.."],                   # dot above
    "̄": [".###."],                   # macron
    "̆": [".#.#.", "..#.."],          # breve (a u shape at this size)
    "̋": ["..#.#", ".#.#."],          # double acute
}
BELOW = {
    "̧": ["..#..", ".##.."],          # cedilla
    "̨": ["...#.", "...##"],          # ogonek
    "̦": ["..#..", ".#..."],          # comma below (Romanian ș ț)
}
# Letters and marks that do not decompose, drawn by hand in the 5x7 style.
EXTRA = {
    "ß": [".##..", "#..#.", "#..#.", "#.##.", "#...#", "#...#", "#.##."],
    "ł": [".##..", "..#..", "..##.", ".##..", "..#..", "..#..", ".###."],
    "Ł": ["#....", "#....", "#.#..", "##...", "#....", "#....", "#####"],
    "ø": [".....", "....#", ".###.", "#..##", "#.#.#", "##..#", ".###.", "#...."],
    "Ø": [".####", "#..##", "#.#.#", "#.#.#", "#.#.#", "##..#", "####."],
    "æ": [".....", ".....", "##.#.", "..#.#", ".####", "#.#..", ".#.##"],
    "Æ": [".####", "#.#..", "#.#..", "#####", "#.#..", "#.#..", "#.###"],
    "œ": [".....", ".....", ".#.#.", "#.#.#", "#.###", "#.#..", ".#.##"],
    "Œ": [".####", "#.#..", "#.#..", "#.###", "#.#..", "#.#..", ".####"],
    "đ": ["...#.", "..###", ".###.", "#..#.", "#..#.", "#..#.", ".###."],
    "Đ": [".###.", ".#..#", ".#..#", "###.#", ".#..#", ".#..#", ".###."],
    "ħ": [".#...", "###..", ".#...", ".###.", ".#..#", ".#..#", ".#..#"],
    "Ħ": ["#...#", "#####", "#...#", "#####", "#...#", "#...#", "#...#"],
    "ı": [".....", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    "«": [".....", ".....", "..#.#", ".#.#.", "#.#..", ".#.#.", "..#.#"],
    "»": [".....", ".....", "#.#..", ".#.#.", "..#.#", ".#.#.", "#.#.."],
    "“": ["..#.#", ".#.#."],
    "”": [".#.#.", "#.#.."],
    "„": [".....", ".....", ".....", ".....", ".....", ".#.#.", "#.#.."],
    "‘": ["...#.", "..#.."],
    "’": ["..#..", ".#..."],
    "‚": [".....", ".....", ".....", ".....", ".....", "..#..", ".#..."],
    "…": [".....", ".....", ".....", ".....", ".....", ".....", "#.#.#"],
    "–": [".....", ".....", ".....", "#####"],
    "—": [".....", ".....", ".....", "#####"],
    "·": [".....", ".....", ".....", "..#.."],
    "€": [".###.", "#...#", "####.", "#....", "####.", "#...#", ".###."],
    "°": [".#...", "#.#..", ".#..."],
}


def _rows(table: dict, char: str) -> list[str] | None:
    rows = table.get(char)
    return list(rows) if rows is not None else None


@lru_cache(maxsize=None)
def composed(char: str, table_id: int = 0) -> tuple[tuple[str, ...], int] | None:
    """(rows, lift) of a 5x7 letter for `char`, or None when only Unifont can draw it.
    lift: rows the glyph reaches above the cap line (an accent on a capital)."""
    from engine.render import _GLYPHS_5X7 as table
    if char in table:
        return tuple(table[char]), 0
    if char in EXTRA:
        return tuple(EXTRA[char]), 0
    if char in "¿¡":
        base = table["?" if char == "¿" else "!"]
        rows = [row[::-1] for row in reversed(base + ["....."] * (7 - len(base)))]
        return tuple(rows), 0
    parts = unicodedata.normalize("NFD", char)
    base, marks = parts[0], parts[1:]
    if not marks or not all(m in ABOVE or m in BELOW for m in marks):
        return None
    if base in "ij" and any(m in ABOVE for m in marks):
        base_rows = ["....."] * 2 + list(table[base])[2:]     # the dot gives way to the accent
    else:
        base_rows = _rows(table, base) or _rows(EXTRA, base)
    if base_rows is None:
        return None
    rows = base_rows + ["....."] * (9 - len(base_rows))
    above = [r for m in marks if m in ABOVE for r in ABOVE[m]]
    below = [r for m in marks if m in BELOW for r in BELOW[m]]
    # A lowercase letter without an ascender has two empty rows on top: the accent goes there.
    free = 0
    while free < 2 and set(rows[free]) == {"."}:
        free += 1
    # A lowercase accent keeps one empty row between itself and the letter (ñ, not "fi").
    # A capital keeps the gap only under a one-row mark (Ö Ė Ā), so it does not grow too tall.
    gap = 1 if free == 2 or len(above) == 1 else 0
    lift = max(0, len(above) + gap - free)
    top = ["....."] * lift + rows
    start = lift + free - len(above) - gap
    for i, mark in enumerate(above):
        top[start + i] = _merge(top[start + i], mark)
    for i, mark in enumerate(below):
        top[lift + 7 + i] = _merge(top[lift + 7 + i], mark)
    return tuple(top), lift


def _merge(row: str, mark: str) -> str:
    return "".join("#" if a == "#" or b == "#" else "." for a, b in zip(row.ljust(5, "."), mark))


@lru_cache(maxsize=1)
def unifont() -> pygame.font.Font | None:
    if not pygame.font.get_init():
        pygame.font.init()
    try:
        return pygame.font.Font(str(UNIFONT), UNIFONT_PX)
    except (OSError, pygame.error):
        return None


def unifont_has(char: str) -> bool:
    font = unifont()
    if font is None:
        return False
    metrics = font.metrics(char)
    return bool(metrics) and metrics[0] is not None


def covered(char: str) -> bool:
    """Can the game draw this character (pixel letters, an accent, or Unifont)?"""
    return char.isspace() or composed(char) is not None or unifont_has(char)


def hd_covers(char: str) -> bool:
    """Characters JetBrains Mono draws: Latin (with every EU accent), Greek, Cyrillic,
    punctuation, currency. Everything else (Chinese) goes to Unifont."""
    code = ord(char)
    return code < 0x0530 or 0x1E00 <= code <= 0x1FFF or 0x2000 <= code <= 0x20CF or \
        0x2100 <= code <= 0x214F


@lru_cache(maxsize=None)
def hd_font(cell_w: int, bold: bool = False, line_px: int = 0) -> pygame.font.Font | None:
    """The largest JetBrains Mono whose letters fit a cell `cell_w` real pixels wide and whose
    descenders stay inside a line `line_px` tall (the old letters' height)."""
    if not pygame.font.get_init():
        pygame.font.init()
    try:
        size = max(6, int(cell_w / 0.6) + 1)
        if line_px:
            size = min(size, int(line_px * 0.84))
        font = pygame.font.Font(str(HD_FONT[bold]), size)
        while size > 6 and font.size("M")[0] > cell_w:
            size -= 1
            font = pygame.font.Font(str(HD_FONT[bold]), size)
        return font
    except (OSError, pygame.error):
        return None


_HD: dict[tuple, pygame.Surface] = {}


def reset() -> None:
    """Forget every loaded font (pygame was shut down and started again: they are dead)."""
    _HD.clear()
    _GLYPHS.clear()
    hd_font.cache_clear()
    unifont.cache_clear()


def hd_glyph(char: str, colour: tuple, cell_w: int, bold: bool = False, line_px: int = 0):
    """(surface, font) of one HD letter, cached."""
    key = (char, tuple(colour), cell_w, bold, line_px)
    font = hd_font(cell_w, bold, line_px)
    if font is None:
        return None, None
    if key not in _HD:
        try:
            _HD[key] = font.render(char, True, colour)
        except pygame.error:                   # a font from before pygame.quit(): reload
            reset()
            font = hd_font(cell_w, bold, line_px)
            _HD[key] = font.render(char, True, colour)
    return _HD[key], font


def unifont_scale(k: int, line_h: int) -> int:
    """Whole-number size of Unifont at window scale k, about the height of a line."""
    return max(1, round(line_h * k / UNIFONT_PX))


_GLYPHS: dict[tuple, pygame.Surface] = {}


def fallback_glyph(char: str, colour: tuple, k: int, line_h: int, cell_w: int) -> pygame.Surface:
    """A Unifont character at scale k, sized to its cells (one or two)."""
    key = (char, tuple(colour), k, line_h, cell_w)
    if key not in _GLYPHS:
        font = unifont()
        if font is None:
            surface = pygame.Surface((cell_w * k, line_h * k), pygame.SRCALPHA)
            gfx.rect(surface, colour, surface.get_rect(), 1)
        else:
            surface = font.render(char, False, colour)
            scale = unifont_scale(k, line_h)
            if scale != 1:
                surface = pygame.transform.scale(
                    surface, (surface.get_width() * scale, surface.get_height() * scale))
            width = cells(char) * cell_w * k
            if surface.get_width() > width:            # small print: squeeze into the cell
                surface = pygame.transform.scale(surface, (width, surface.get_height()))
        _GLYPHS[key] = surface
    return _GLYPHS[key]
