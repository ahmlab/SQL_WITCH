"""The 320x180 canvas, integer scaling, the palette and the pixel font (design doc 6.4, 7.1, 7.2).

Everything in the game draws onto one small surface. Only present() touches the window: it
scales the canvas by a whole number with nearest-neighbour sampling and letterboxes the rest,
so pixels stay square and nothing shimmers.

Text sits on a 4-pixel character grid, so the 146 px right page holds about 36 characters,
exactly the PAGE_WIDTH of the Rule of the Page. It is monospaced on purpose: character counts
and pixels then always agree. The letters themselves are drawn at the window's real resolution
with a 5x7 font (see Canvas), which keeps them sharp and legible at any scale; the chunky
3x5 font is kept for surfaces that are not the main canvas. Small print packs the same 5x7
letters on a 3-pixel grid, and big titles draw them as blocks of pixel art.

STATUS: canvas, scaling, palette, sharp text layer (5x7), small print, big titles, helpers.
"""

from __future__ import annotations

import unicodedata

import pygame

from engine import gfx

from engine import fonts
from i18n.width import cells, text_cells

LOGICAL_W, LOGICAL_H = 320, 180

# ------------------------------------------------------------------ palette (design doc 7.2)
# The 32 colours sampled from figure 11, in the figure's order. Never draw outside them.
INK = (0x1a, 0x14, 0x23)
NIGHT = (0x2b, 0x21, 0x40)
DUSK = (0x3e, 0x2e, 0x5c)
VIOLET = (0x5b, 0x43, 0x88)
LAVENDER = (0x8a, 0x63, 0xc9)
LILAC = (0xc6, 0xa6, 0xf0)
SAND = (0xb8, 0x9a, 0x6a)
PARCHMENT = (0xe8, 0xd5, 0xa8)
CREAM = (0xf6, 0xec, 0xd0)
BARK = (0x4a, 0x2f, 0x25)
LEATHER = (0x7a, 0x4b, 0x33)
AMBER = (0xb0, 0x70, 0x20)
GOLD = (0xf2, 0xb3, 0x3d)
BUTTER = (0xff, 0xe0, 0x8a)
WINE = (0x8c, 0x2a, 0x3a)
RED = (0xd1, 0x4b, 0x4b)
FOREST = (0x2e, 0x7a, 0x4a)
GRASS = (0x5f, 0xbf, 0x6a)
MINT = (0xaa, 0xe6, 0x96)
TEAL = (0x1c, 0x70, 0x6c)
AQUA = (0x3f, 0xb6, 0xb0)
FOAM = (0x9f, 0xf0, 0xe0)
NAVY = (0x28, 0x40, 0x8c)
BLUE = (0x3c, 0x6f, 0xd1)
SKY = (0x86, 0xb8, 0xf0)
SLATE = (0x54, 0x4e, 0x63)
GREY = (0x8a, 0x84, 0x97)
WHITE = (0xfb, 0xf7, 0xef)
CLAY = (0xd4, 0x9b, 0x7d)
PEACH = (0xf2, 0xc8, 0xa5)
RUST = (0x70, 0x2c, 0x28)
BRICK = (0xa8, 0x48, 0x34)

PALETTE = [INK, NIGHT, DUSK, VIOLET, LAVENDER, LILAC, SAND, PARCHMENT,
           CREAM, BARK, LEATHER, AMBER, GOLD, BUTTER, WINE, RED,
           FOREST, GRASS, MINT, TEAL, AQUA, FOAM, NAVY, BLUE,
           SKY, SLATE, GREY, WHITE, CLAY, PEACH, RUST, BRICK]

# Element colours for projectiles and highlights.
ELEMENT_COLOURS = {
    "Fire": RED, "Tide": BLUE, "Nature": GRASS, "Storm": GOLD, "Arcane": LAVENDER,
    "Earth": LEATHER, "Frost": SKY, "Wind": MINT, "Light": BUTTER, "Shadow": DUSK,
    None: GREY,
}

# ------------------------------------------------------------------ the pixel font

GLYPH_W, GLYPH_H = 3, 6          # 5 rows above the baseline + 1 descender row
ADVANCE = GLYPH_W + 1            # one pixel of space between characters
LINE_H = GLYPH_H + 1

# Small print: for text that must stay out of the way (the guardian's book). Its letters keep
# the height of normal text; only their width and the space between them shrink.
SMALL_ADVANCE, SMALL_LINE_H = 3, 6

# Each glyph: rows top to bottom, '#' = ink. Rows missing at the end are blank.
_GLYPHS = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"], "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"], "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "###", "#..", "###"], "F": ["###", "#..", "###", "#..", "#.."],
    "G": [".##", "#..", "#.#", "#.#", ".##"], "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"], "J": ["..#", "..#", "..#", "#.#", ".#."],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"], "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"], "N": ["##.", "#.#", "#.#", "#.#", "#.#"],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."], "P": ["##.", "#.#", "##.", "#..", "#.."],
    "Q": [".#.", "#.#", "#.#", "###", ".##"], "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."], "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", ".##"], "V": ["#.#", "#.#", "#.#", ".#.", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"], "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."], "Z": ["###", "..#", ".#.", "#..", "###"],
    "a": ["...", ".##", "#.#", "#.#", ".##"], "b": ["#..", "##.", "#.#", "#.#", "##."],
    "c": ["...", ".##", "#..", "#..", ".##"], "d": ["..#", ".##", "#.#", "#.#", ".##"],
    "e": ["...", ".#.", "###", "#..", ".##"], "f": ["..#", ".#.", "###", ".#.", ".#."],
    "g": ["...", ".##", "#.#", ".##", "..#", "##."], "h": ["#..", "##.", "#.#", "#.#", "#.#"],
    "i": [".#.", "...", ".#.", ".#.", ".#."], "j": ["..#", "...", "..#", "..#", "#.#", ".#."],
    "k": ["#..", "#.#", "##.", "##.", "#.#"], "l": ["##.", ".#.", ".#.", ".#.", "###"],
    "m": ["...", "###", "###", "#.#", "#.#"], "n": ["...", "##.", "#.#", "#.#", "#.#"],
    "o": ["...", ".#.", "#.#", "#.#", ".#."], "p": ["...", "##.", "#.#", "#.#", "##.", "#.."],
    "q": ["...", ".##", "#.#", "#.#", ".##", "..#"], "r": ["...", "#.#", "##.", "#..", "#.."],
    "s": ["...", ".##", "#..", "..#", "##."], "t": [".#.", "###", ".#.", ".#.", "..#"],
    "u": ["...", "#.#", "#.#", "#.#", ".##"], "v": ["...", "#.#", "#.#", "#.#", ".#."],
    "w": ["...", "#.#", "#.#", "###", "###"], "x": ["...", "#.#", ".#.", ".#.", "#.#"],
    "y": ["...", "#.#", "#.#", ".##", "..#", "##."], "z": ["...", "###", ".##", "#..", "###"],
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"], "3": ["##.", "..#", ".#.", "..#", "##."],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "##.", "..#", "##."],
    "6": [".##", "#..", "###", "#.#", "###"], "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "##."],
    " ": [], "!": [".#.", ".#.", ".#.", "...", ".#."], '"': ["#.#", "#.#"],
    "#": ["#.#", "###", "#.#", "###", "#.#"], "$": [".##", "##.", ".#.", ".##", "##."],
    "%": ["#.#", "..#", ".#.", "#..", "#.#"], "&": [".#.", "#.#", ".#.", "#.#", ".##"],
    "'": [".#.", ".#."], "(": ["..#", ".#.", ".#.", ".#.", "..#"],
    ")": ["#..", ".#.", ".#.", ".#.", "#.."], "*": [".#.", "###", ".#.", "#.#"],
    "+": ["...", ".#.", "###", ".#."], ",": ["...", "...", "...", "...", ".#.", "#.."],
    "-": ["...", "...", "###"], ".": ["...", "...", "...", "...", ".#."],
    "/": ["..#", "..#", ".#.", "#..", "#.."], ":": ["...", ".#.", "...", ".#."],
    ";": ["...", ".#.", "...", ".#.", "#.."], "<": ["..#", ".#.", "#..", ".#.", "..#"],
    "=": ["...", "###", "...", "###"], ">": ["#..", ".#.", "..#", ".#.", "#.."],
    "?": ["##.", "..#", ".#.", "...", ".#."], "@": [".#.", "#.#", "###", "#..", ".##"],
    "[": ["##.", "#..", "#..", "#..", "##."], "\\": ["#..", "#..", ".#.", "..#", "..#"],
    "]": [".##", "..#", "..#", "..#", ".##"], "^": [".#.", "#.#"],
    "_": ["...", "...", "...", "...", "###"], "`": ["#..", ".#."],
    "{": [".##", ".#.", "##.", ".#.", ".##"], "|": [".#.", ".#.", ".#.", ".#.", ".#."],
    "}": ["##.", ".#.", ".##", ".#.", "##."], "~": ["...", ".##", "##."],
}
_UNKNOWN = ["###", "#.#", "#.#", "#.#", "###"]


# A 5x7 font for the text layer: same 4-pixel character grid, far more detail per letter.
# Rows top to bottom; rows 7 and 8 are descenders (g, j, p, q, y, comma).
_GLYPHS_5X7 = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
    "b": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "####."],
    "c": [".....", ".....", ".###.", "#....", "#....", "#...#", ".###."],
    "d": ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
    "e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
    "f": ["..##.", ".#..#", ".#...", "###..", ".#...", ".#...", ".#..."],
    "g": [".....", ".....", ".####", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
    "h": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "i": ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    "j": ["...#.", ".....", "..##.", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "k": ["#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."],
    "l": [".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "m": [".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"],
    "n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "o": [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
    "p": [".....", ".....", "####.", "#...#", "#...#", "#...#", "####.", "#....", "#...."],
    "q": [".....", ".....", ".####", "#...#", "#...#", "#...#", ".####", "....#", "....#"],
    "r": [".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."],
    "s": [".....", ".....", ".####", "#....", ".###.", "....#", "####."],
    "t": [".#...", ".#...", "###..", ".#...", ".#...", ".#..#", "..##."],
    "u": [".....", ".....", "#...#", "#...#", "#...#", "#..##", ".##.#"],
    "v": [".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "w": [".....", ".....", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#."],
    "x": [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    "y": [".....", ".....", "#...#", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
    "z": [".....", ".....", "#####", "...#.", "..#..", ".#...", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    " ": [],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    '"': [".#.#.", ".#.#.", ".#.#."],
    "#": [".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."],
    "$": ["..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."],
    "%": ["##...", "##..#", "...#.", "..#..", ".#...", "#..##", "...##"],
    "&": [".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
    "'": ["..#..", "..#..", ".#..."],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "*": [".....", "..#..", "#.#.#", ".###.", "#.#.#", "..#..", "....."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    ",": [".....", ".....", ".....", ".....", ".....", ".##..", ".##..", "..#..", ".#..."],
    "-": [".....", ".....", ".....", "#####"],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    "/": [".....", "....#", "...#.", "..#..", ".#...", "#....", "....."],
    ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    ";": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "..#..", ".#..."],
    "<": ["...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."],
    "=": [".....", ".....", "#####", ".....", "#####"],
    ">": [".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    "@": [".###.", "#...#", "....#", ".##.#", "#.#.#", "#.#.#", ".###."],
    "[": [".###.", ".#...", ".#...", ".#...", ".#...", ".#...", ".###."],
    "\\": [".....", "#....", ".#...", "..#..", "...#.", "....#", "....."],
    "]": [".###.", "...#.", "...#.", "...#.", "...#.", "...#.", ".###."],
    "^": ["..#..", ".#.#.", "#...#"],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "`": [".#...", "..#..", "...#."],
    "{": ["...#.", "..#..", "..#..", ".#...", "..#..", "..#..", "...#."],
    "|": ["..#..", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "}": [".#...", "..#..", "..#..", "...#.", "..#..", "..#..", ".#..."],
    "~": [".....", ".....", ".#...", "#.#.#", "...#."],
}
_UNKNOWN_5X7 = ["#####", "#...#", "#...#", "#...#", "#...#", "#...#", "#####"]
FINE_W, FINE_H, FINE_CAP = 5, 9, 7


def fine_pixel(k: int, cell: int = ADVANCE) -> int:
    """Size in screen pixels of one dot of the 5x7 font at window scale k.
    It stays a whole number (crisp) and the letter, bold stroke included, keeps at least one
    pixel of space inside its cell (4k pixels wide, or 3k for small print)."""
    dot = max(1, round(k * 0.6))
    while dot > 1 and 5 * dot + bold_px(dot) > cell * k - 1:
        dot -= 1
    return dot


def bold_px(dot: int) -> int:
    """Strokes are widened by half a dot: thin 1-dot strokes are hard to read when small."""
    return max(1, dot // 2)


def small_print_dots(k: int) -> tuple[int, int, int]:
    """(dot width, dot height, bold) of small print at window scale k.
    The width must fit the 3k-pixel cell; the height stays that of normal text as long as
    the letter, descender included, fits its line. On small windows the letters are therefore
    narrower than tall, instead of shrinking to half their size."""
    dot_x = fine_pixel(k, SMALL_ADVANCE)
    dot_y = max(dot_x, min(fine_pixel(k), SMALL_LINE_H * k // FINE_H))
    bold = bold_px(dot_x)
    if 5 * dot_x + bold > SMALL_ADVANCE * k - 1:      # tiny windows: no room for the bold stroke
        bold = 0
    return dot_x, dot_y, bold


WORLD_SCALE = 4                  # real pixels per logical pixel: 320x180 -> 1280x720 (HD 720p)


class Canvas(pygame.Surface):
    """The game surface: laid out in logical 320x180 coordinates, stored at 1280x720.

    Scenes draw as they always did, in the 320x180 grid (the page is 36 characters wide, every
    box keeps its place), through engine/gfx.py and the methods below, which multiply by
    `scale`. Pixel art drawn at 1x is enlarged with hard edges, so it looks as before; HD art
    (gfx.blit_hd, fractional coordinates, quarter-pixel lines) uses all 1280x720 pixels.

    Text is not painted into the canvas: it is recorded, and drawn on top of the finished HD
    frame (draw_text_layer), letter by letter in the same 4-pixel grid.
    """

    def __init__(self, size=(LOGICAL_W, LOGICAL_H), scale: int = WORLD_SCALE):
        super().__init__((size[0] * scale, size[1] * scale))
        self.scale = scale
        self.logical = pygame.Rect(0, 0, *size)
        self._clip = None
        self.ops: list[tuple] = []

    def begin_frame(self) -> None:
        self.ops.clear()

    def texts(self) -> list[str]:
        """Every string drawn this frame (handy for tests)."""
        return [op[1] for op in self.ops if op[0] in ("text", "small")]

    # ------------------------------------------------------------ the logical surface

    def get_size(self):
        return self.logical.size

    def get_width(self):
        return self.logical.w

    def get_height(self):
        return self.logical.h

    def get_rect(self, **kw):
        rect = self.logical.copy()
        for key, value in kw.items():
            setattr(rect, key, value)
        return rect

    def _hd(self, rect) -> pygame.Rect:
        rect = pygame.Rect(rect)
        s = self.scale
        return pygame.Rect(rect.x * s, rect.y * s, rect.w * s, rect.h * s)

    def fill(self, colour, rect=None, special_flags=0):
        return super().fill(colour, None if rect is None else self._hd(rect), special_flags)

    def set_at(self, pos, colour):
        s = self.scale
        super().fill(colour, (int(pos[0]) * s, int(pos[1]) * s, s, s))

    def get_at(self, pos):
        s = self.scale
        return super().get_at((int(pos[0]) * s, int(pos[1]) * s))

    def scroll(self, dx=0, dy=0):
        super().scroll(dx * self.scale, dy * self.scale)

    def set_clip(self, rect=None):
        self._clip = None if rect is None else pygame.Rect(rect)
        super().set_clip(None if rect is None else self._hd(rect))

    def get_clip(self):
        return self._clip.copy() if self._clip is not None else self.logical.copy()

    def blit(self, source, dest, area=None, special_flags=0):
        """A logical (1x) image at a logical position, enlarged with hard edges."""
        s = self.scale
        if area is not None:
            area = pygame.Rect(area)
            source = source.subsurface(area.clip(source.get_rect()))
        x, y = (dest.x, dest.y) if isinstance(dest, pygame.Rect) else dest
        w, h = source.get_size()
        big = pygame.transform.scale(source, (w * s, h * s))
        super().blit(big, (round(x * s), round(y * s)), None, special_flags)
        return pygame.Rect(int(x), int(y), w, h)

    def hd_pixels(self) -> pygame.Surface:
        """The real 1280x720 pixels (for composing the frame)."""
        return self


class PixelFont:
    """Draws text. On a Canvas the text goes to the sharp text layer; on any other surface
    (and for big scaled titles) it is drawn right away with the chunky 3x5 glyphs."""

    def __init__(self):
        self._cache: dict[tuple, pygame.Surface] = {}

    def glyph(self, char: str, colour: tuple) -> pygame.Surface:
        key = ("lo", char, tuple(colour))
        if key not in self._cache:
            # 3x5 letters have no room for accents: an accented letter shows its base letter.
            rows = _GLYPHS.get(char) or _GLYPHS.get(unicodedata.normalize("NFD", char)[:1],
                                                    _UNKNOWN)
            self._cache[key] = self._build(rows, GLYPH_W, GLYPH_H, colour, 1)
        return self._cache[key]

    def fine(self, char: str, colour: tuple, dot: int, dot_y: int | None = None,
             bold: int | None = None) -> tuple[pygame.Surface, int] | None:
        """(glyph, lift in screen pixels) of a pixel letter, accents included, or None when
        only the fallback font (engine/fonts.py) can draw the character."""
        made = fonts.composed(char)
        if made is None:
            return None
        rows, lift = made
        dot_y = dot if dot_y is None else dot_y
        bold = bold_px(dot) if bold is None else bold
        key = ("fine", char, tuple(colour), dot, dot_y, bold)
        if key not in self._cache:
            self._cache[key] = self._build(list(rows), FINE_W, max(FINE_H, len(rows)), colour,
                                           dot, bold, dot_y)
        return self._cache[key], lift * dot_y

    def fine_glyph(self, char: str, colour: tuple, dot: int, dot_y: int | None = None,
                   bold: int | None = None) -> pygame.Surface:
        """A 5x7 letter with dot x dot_y screen pixels per dot (narrower for small print)."""
        dot_y = dot if dot_y is None else dot_y
        bold = bold_px(dot) if bold is None else bold
        key = ("hi", char, tuple(colour), dot, dot_y, bold)
        if key not in self._cache:
            self._cache[key] = self._build(_GLYPHS_5X7.get(char, _UNKNOWN_5X7), FINE_W,
                                           FINE_H, colour, dot, bold, dot_y)
        return self._cache[key]

    @staticmethod
    def _build(rows, w, h, colour, dot, bold=0, dot_y=None) -> pygame.Surface:
        dot_y = dot if dot_y is None else dot_y
        surface = pygame.Surface((w * dot + bold, h * dot_y), pygame.SRCALPHA)
        for y, row in enumerate(rows):
            for x, bit in enumerate(row):
                if bit == "#":
                    surface.fill(colour, (x * dot, y * dot_y, dot + bold, dot_y))
        return surface

    def width(self, text: str, scale: int = 1, small: bool = False) -> int:
        advance = SMALL_ADVANCE if small else ADVANCE
        return max(0, text_cells(text) * advance - 1) * scale

    def draw(self, surface: pygame.Surface, text: str, pos: tuple[float, float],
             colour: tuple, scale: int = 1, shadow: tuple | None = None,
             small: bool = False) -> int:
        """Draw text with its top-left at pos. Returns the width drawn, in logical pixels."""
        x, y = snap(pos[0]), snap(pos[1])
        if shadow is not None:
            self.draw(surface, text, (x, y + scale), shadow, scale, small=small)  # drop shadow
        if isinstance(surface, Canvas) and scale == 1:
            kind = "small" if small else "text"
            surface.ops.append((kind, text, x, y, tuple(colour), surface.get_clip()))
            return self.width(text, small=small)
        advance = SMALL_ADVANCE if small else ADVANCE
        col = 0
        for char in text:
            glyph = self.glyph(char, colour)
            if scale != 1:
                glyph = pygame.transform.scale(glyph, (GLYPH_W * scale, GLYPH_H * scale))
            surface.blit(glyph, (x + col * advance * scale, y))
            col += cells(char)
        return self.width(text, scale, small)

    # Big titles use the detailed 5x7 letters as pixel art, each dot a dot x dot block.
    # The 3x5 letters scaled up are too coarse for a title: their W and H differ by one pixel.

    @staticmethod
    def big_width(text: str, dot: int) -> int:
        return max(0, text_cells(text) * (FINE_W + 1) - 1) * dot

    def draw_big(self, surface: pygame.Surface, text: str, pos: tuple[float, float],
                 colour: tuple, dot: int = 3, shadow: tuple | None = None,
                 outline: tuple | None = None) -> int:
        """Draw a title with its top-left at pos, straight into the pixel art. A one-pixel
        outline keeps it readable over any backdrop; the shadow sits one pixel below it."""
        x, y = snap(pos[0]), snap(pos[1])
        if outline is not None:
            for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1),
                           (-1, 2), (0, 2), (1, 2)):
                self.draw_big(surface, text, (x + dx, y + dy), outline, dot)
        if shadow is not None:
            self.draw_big(surface, text, (x, y + 1), shadow, dot)
        col = 0
        for char in text:
            key = ("big", char, tuple(colour), dot)
            if key not in self._cache:
                made = fonts.composed(char)
                if made is not None:
                    rows, lift = made
                    glyph = self._build(list(rows), FINE_W, max(FINE_H, len(rows)), colour, dot)
                    self._cache[key] = (glyph, lift * dot)
                else:                                  # a Chinese title: Unifont, as big
                    glyph = fonts.fallback_glyph(char, colour, 1, fonts.UNIFONT_PX, 8)
                    times = max(1, round(FINE_H * dot / fonts.UNIFONT_PX))   # whole pixels
                    size = (glyph.get_width() * times, glyph.get_height() * times)
                    self._cache[key] = (pygame.transform.scale(glyph, size), 0)
            glyph, lift = self._cache[key]
            surface.blit(glyph, (x + col * (FINE_W + 1) * dot, y - lift))
            col += cells(char)
        return self.big_width(text, dot)


_FONT: PixelFont | None = None


def font() -> PixelFont:
    """The shared font. Built lazily so importing this module needs no display."""
    global _FONT
    if _FONT is None:
        _FONT = PixelFont()
    return _FONT


def snap(value: float) -> int:
    """Round before drawing, so sprites move in whole pixels and never shimmer."""
    return int(round(value))


def draw_coloured(surface: pygame.Surface, text: str, colours: list[tuple],
                  pos: tuple[int, int], small: bool = False) -> None:
    """Draw text where each character has its own colour (syntax colouring), in runs."""
    f, x, start = font(), pos[0], 0
    advance = SMALL_ADVANCE if small else ADVANCE
    for i in range(1, len(text) + 1):
        if i == len(text) or colours[i] != colours[start]:
            f.draw(surface, text[start:i], (x + text_cells(text[:start]) * advance, pos[1]),
                   colours[start], small=small)
            start = i


def cover(surface: pygame.Surface, rect: pygame.Rect, rgba: tuple) -> None:
    """A translucent box that also hides text drawn earlier (e.g. the F1 overlay)."""
    rect = pygame.Rect(rect)
    if isinstance(surface, Canvas):
        surface.ops.append(("fill", rect, tuple(rgba), surface.get_clip()))
        return
    box = pygame.Surface(rect.size, pygame.SRCALPHA)
    box.fill(rgba)
    surface.blit(box, rect.topleft)


HEAVY_TEXT = [False]              # settings: the large Grimoire font (heavier letters)
GRIMOIRE_TOP = 104                # canvas rows from here down are the Grimoire's pages


def draw_text_layer(frame: pygame.Surface, ops: list[tuple], k: int) -> None:
    """Replay the frame's text on the scaled frame, at k screen pixels per game pixel."""
    f = font()
    dot = fine_pixel(k)
    dy = (GLYPH_H - 1) * k // 2 - FINE_CAP * dot // 2      # centre the 5x7 cap on the old one
    small_dots = small_print_dots(k)
    small_dy = max(0, (SMALL_LINE_H * k - FINE_H * small_dots[1]) // 2)   # centred in its line
    for op in ops:
        clip = op[-1]
        frame.set_clip(pygame.Rect(clip.x * k, clip.y * k, clip.w * k, clip.h * k))
        if op[0] == "fill":
            rect, rgba = op[1], op[2]
            box = pygame.Surface((rect.w * k, rect.h * k), pygame.SRCALPHA)
            box.fill(rgba)
            frame.blit(box, (rect.x * k, rect.y * k))
            continue
        kind, text, x, y, colour, _ = op
        small = kind == "small"
        advance, top = (SMALL_ADVANCE, small_dy) if small else (ADVANCE, dy)
        line_h = SMALL_LINE_H if small else LINE_H
        heavy = HEAVY_TEXT[0] and y >= GRIMOIRE_TOP and not small
        col = 0
        for char in text:
            cx = (x + col * advance) * k
            col += cells(char)
            if char == " ":
                continue
            if k >= fonts.HD_FROM_K and fonts.hd_covers(char):
                glyph, hd = fonts.hd_glyph(char, colour, advance * k, heavy, line_h * k)
                if glyph is not None:
                    # The baseline where the old letters had theirs: room below for descenders.
                    top = y * k + round(line_h * k * 0.72) - hd.get_ascent()
                    frame.blit(glyph, (cx + (advance * k - glyph.get_width()) // 2, top))
                    continue
            made = None if k == 1 else (f.fine(char, colour, *small_dots) if small
                                        else f.fine(char, colour, dot, None,
                                                    bold_px(dot) + (1 if heavy else 0)))
            if made is not None:
                glyph, lift = made
                frame.blit(glyph, (cx, y * k + top - lift))
            elif k == 1 and fonts.composed(char) is not None:   # no room for detail at 1x
                frame.blit(f.glyph(char, colour), (cx, y))
            else:                                    # Chinese, Greek, Cyrillic: Unifont
                glyph = fonts.fallback_glyph(char, colour, k, line_h, advance)
                room = cells(char) * advance * k                # centred in its cell(s)
                frame.blit(glyph, (cx + max(0, room - glyph.get_width()) // 2,
                                   y * k + (line_h * k - glyph.get_height()) // 2))
    frame.set_clip(None)


# ------------------------------------------------------------------ the window

def fit(window_size: tuple[int, int]) -> tuple[int, tuple[int, int]]:
    """The largest whole-number scale that fits the window, and the letterbox offset."""
    w, h = window_size
    k = max(1, min(w // LOGICAL_W, h // LOGICAL_H))
    return k, ((w - LOGICAL_W * k) // 2, (h - LOGICAL_H * k) // 2)


def letterbox(window_size: tuple[int, int], fill: bool = False
              ) -> tuple[int, tuple[int, int], tuple[int, int]]:
    """How the 320x180 frame sits in a window: (k for the text layer, frame size, offset).
    Integer scaling with black bars by default; fill: the largest size that keeps the aspect,
    not a whole multiple (no bars on 16:9, a slight softness instead)."""
    w, h = window_size
    k, offset = fit(window_size)
    if not fill:
        return k, (LOGICAL_W * k, LOGICAL_H * k), offset
    s = min(w / LOGICAL_W, h / LOGICAL_H)
    size = (round(LOGICAL_W * s), round(LOGICAL_H * s))
    return max(1, int(s)), size, ((w - size[0]) // 2, (h - size[1]) // 2)


def desktop_size() -> tuple[int, int]:
    """The size of the monitor the game opens on (not of the game's window)."""
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes and sizes[0][0] > 0:
            return sizes[0]
    except (AttributeError, pygame.error):
        pass
    info = pygame.display.Info()
    return info.current_w, info.current_h


class Screen:
    """Owns the window and the logical canvas. Scenes draw on .canvas, then call present().
    Windowed (a whole-number scale) or fullscreen (the whole display, letterboxed at a whole
    number by default, or filled); set_display() switches at any time."""

    def __init__(self, scale: int | None = None, title: str = "SQL Witch",
                 display: str = "windowed", fill: bool = False):
        pygame.display.set_caption(title)
        self.canvas = Canvas()
        self.shake = 0           # frames of screen shake left (design doc 7.3)
        self.mode, self.fill, self.scale = "windowed", False, scale
        self.set_display(display, scale, fill)

    def set_display(self, mode: str = "windowed", scale: int | None = None,
                    fill: bool = False) -> None:
        self.fill = fill
        if mode == "fullscreen":
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            if scale is None:
                # The monitor's size, never the window's: measured from the window, the
                # "largest that fits" would shrink a little every time the display is set.
                w, h = desktop_size()
                scale = fit((w - 80, h - 120))[0]
                if scale >= WORLD_SCALE:          # a whole multiple of 1280x720: the crispest
                    scale -= scale % WORLD_SCALE
            self.window = pygame.display.set_mode((LOGICAL_W * scale, LOGICAL_H * scale),
                                                  pygame.RESIZABLE)
            self.scale = scale
        self.mode = mode

    def to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        """A window pixel (e.g. a mouse click) -> a canvas pixel, undoing scale and letterbox."""
        _, size, (ox, oy) = letterbox(self.window.get_size(), self.fill)
        return (pos[0] - ox) * LOGICAL_W // max(1, size[0]), \
            (pos[1] - oy) * LOGICAL_H // max(1, size[1])

    def compose(self) -> tuple[pygame.Surface, int]:
        """The finished frame: the HD canvas with its text drawn at HD resolution, then fitted
        to the window: a whole multiple when one fits, else smoothly (fill, or a window smaller
        than 1280x720)."""
        canvas = self.canvas
        frame = pygame.Surface(canvas.get_size() if not isinstance(canvas, Canvas) else
                               (LOGICAL_W * canvas.scale, LOGICAL_H * canvas.scale))
        frame.blit(canvas if not isinstance(canvas, Canvas) else canvas.hd_pixels(), (0, 0))
        hd = canvas.scale if isinstance(canvas, Canvas) else 1
        draw_text_layer(frame, canvas.ops if isinstance(canvas, Canvas) else [], hd)
        _, size, _ = letterbox(self.window.get_size(), self.fill)
        if size != frame.get_size():
            if size[0] % frame.get_width() == 0 and size[1] % frame.get_height() == 0:
                frame = pygame.transform.scale(frame, size)        # a whole multiple: crisp
            else:
                frame = pygame.transform.smoothscale(frame, size)
        return frame, hd

    def present(self, rng=None) -> None:
        frame, k = self.compose()
        _, _, (ox, oy) = letterbox(self.window.get_size(), self.fill)
        if self.shake > 0 and rng is not None:
            ox += rng.choice((-1, 1)) * rng.randint(1, 2) * k
            oy += rng.choice((-1, 1)) * rng.randint(0, 1) * k
            self.shake -= 1
        self.window.fill((0, 0, 0))                     # the letterbox
        self.window.blit(frame, (ox, oy))
        pygame.display.flip()


# ------------------------------------------------------------------ small helpers

def panel(surface: pygame.Surface, rect: pygame.Rect, fill=CREAM, border=INK,
          inner=PARCHMENT) -> None:
    """A bordered box in the style of the battle-screen mock-up (design doc 4.4)."""
    gfx.rect(surface, border, rect)
    gfx.rect(surface, fill, rect.inflate(-2, -2))
    gfx.line(surface, inner, (rect.left + 1, rect.bottom - 2),
                     (rect.right - 2, rect.bottom - 2))


# HP bars change colour as they empty, so danger reads at a glance (same rule for both sides).
HP_WARN, HP_DANGER = 0.5, 0.25           # below half: orange; below a quarter: red


HP_COLOURS = [GRASS, GOLD, RED]          # healthy, below half, below a quarter (set_palette)
_NORMAL_ELEMENTS = dict(ELEMENT_COLOURS)


def hp_colour(value: float, maximum: float) -> tuple:
    """Green from full down to half, orange below half, red below a quarter (or the
    colour-blind palette's three colours)."""
    ratio = value / maximum if maximum else 0.0
    if ratio < HP_DANGER:
        return HP_COLOURS[2]
    if ratio < HP_WARN:
        return HP_COLOURS[1]
    return HP_COLOURS[0]


def set_palette(name: str, palettes: dict) -> None:
    """A colour-blind palette for the HP bars and the element colours (data/accessibility.json),
    always picked from the game's 32 colours."""
    chosen = palettes.get(name) or {}
    HP_COLOURS[:] = [globals()[c] for c in chosen.get("hp", ("GRASS", "GOLD", "RED"))]
    ELEMENT_COLOURS.clear()
    ELEMENT_COLOURS.update(_NORMAL_ELEMENTS)
    ELEMENT_COLOURS.update({element: globals()[c]
                            for element, c in chosen.get("elements", {}).items()})


def meter(surface: pygame.Surface, rect: pygame.Rect, value: int, maximum: int,
          colour: tuple, back=SLATE) -> None:
    """An HP or MP bar. The filled width is a whole number of pixels."""
    gfx.rect(surface, INK, rect)
    gfx.rect(surface, back, rect.inflate(-2, -2))
    inner = rect.inflate(-2, -2)
    filled = snap(inner.width * value / maximum) if maximum else 0
    if filled > 0:
        gfx.rect(surface, colour, (inner.left, inner.top, filled, inner.height))
