"""The 320x180 canvas, integer scaling, the palette and the pixel font (design doc 6.4, 7.1, 7.2).

Everything in the game draws onto one small surface. Only present() touches the window: it
scales the canvas by a whole number with nearest-neighbour sampling and letterboxes the rest,
so pixels stay square and nothing shimmers.

The font is a built-in 3x5 bitmap font (4 px per character), so the 146 px right page holds
about 36 characters, exactly the PAGE_WIDTH of the Rule of the Page. It is monospaced on
purpose: character counts and pixels then always agree.

STATUS: step 5 done - canvas, scaling, palette, pixel font, small drawing helpers.
"""

from __future__ import annotations

import pygame

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


class PixelFont:
    """Draws the bitmap glyphs; each (character, colour) is built once and cached."""

    def __init__(self):
        self._cache: dict[tuple[str, tuple], pygame.Surface] = {}

    def glyph(self, char: str, colour: tuple) -> pygame.Surface:
        key = (char, tuple(colour))
        if key not in self._cache:
            rows = _GLYPHS.get(char, _UNKNOWN)
            surface = pygame.Surface((GLYPH_W, GLYPH_H), pygame.SRCALPHA)
            for y, row in enumerate(rows):
                for x, bit in enumerate(row):
                    if bit == "#":
                        surface.set_at((x, y), colour)
            self._cache[key] = surface
        return self._cache[key]

    def width(self, text: str, scale: int = 1) -> int:
        return max(0, len(text) * ADVANCE - 1) * scale

    def draw(self, surface: pygame.Surface, text: str, pos: tuple[float, float],
             colour: tuple, scale: int = 1, shadow: tuple | None = None) -> int:
        """Draw text with its top-left at pos. Returns the width drawn, in pixels."""
        x, y = snap(pos[0]), snap(pos[1])
        if shadow is not None:
            self.draw(surface, text, (x, y + scale), shadow, scale)   # drop shadow
        for i, char in enumerate(text):
            glyph = self.glyph(char, colour)
            if scale != 1:
                glyph = pygame.transform.scale(glyph, (GLYPH_W * scale, GLYPH_H * scale))
            surface.blit(glyph, (x + i * ADVANCE * scale, y))
        return self.width(text, scale)


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


# ------------------------------------------------------------------ the window

def fit(window_size: tuple[int, int]) -> tuple[int, tuple[int, int]]:
    """The largest whole-number scale that fits the window, and the letterbox offset."""
    w, h = window_size
    k = max(1, min(w // LOGICAL_W, h // LOGICAL_H))
    return k, ((w - LOGICAL_W * k) // 2, (h - LOGICAL_H * k) // 2)


class Screen:
    """Owns the window and the logical canvas. Scenes draw on .canvas, then call present()."""

    def __init__(self, scale: int | None = None, title: str = "SQL Witch"):
        if scale is None:
            info = pygame.display.Info()
            scale = fit((info.current_w - 80, info.current_h - 120))[0]
        self.window = pygame.display.set_mode((LOGICAL_W * scale, LOGICAL_H * scale),
                                              pygame.RESIZABLE)
        pygame.display.set_caption(title)
        self.canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
        self.shake = 0           # frames of screen shake left (design doc 7.3)

    def present(self, rng=None) -> None:
        k, (ox, oy) = fit(self.window.get_size())
        # pygame.transform.scale is nearest-neighbour: exactly what pixel art needs.
        frame = pygame.transform.scale(self.canvas, (LOGICAL_W * k, LOGICAL_H * k))
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
    pygame.draw.rect(surface, border, rect)
    pygame.draw.rect(surface, fill, rect.inflate(-2, -2))
    pygame.draw.line(surface, inner, (rect.left + 1, rect.bottom - 2),
                     (rect.right - 2, rect.bottom - 2))


def meter(surface: pygame.Surface, rect: pygame.Rect, value: int, maximum: int,
          colour: tuple, back=SLATE) -> None:
    """An HP or MP bar. The filled width is a whole number of pixels."""
    pygame.draw.rect(surface, INK, rect)
    pygame.draw.rect(surface, back, rect.inflate(-2, -2))
    inner = rect.inflate(-2, -2)
    filled = snap(inner.width * value / maximum) if maximum else 0
    if filled > 0:
        pygame.draw.rect(surface, colour, (inner.left, inner.top, filled, inner.height))
