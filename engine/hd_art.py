"""HD art, drawn by code at full resolution (four real pixels per logical pixel).

Each piece is painted once into a surface at HD size (cached; animated pieces cache their
frames) and placed with gfx.blit_hd at a logical position, so the scenes keep their layout.
Colours come from the game's palette, with gradients between palette colours for skies, light
and volume: the same look, with the detail the 320x180 grid could not hold.

These are the programmer's art (the author's choice: drawn by code now); the artist's art can
replace any piece through the same functions.

STATUS: glade and keep backdrops, the Asterisk Slime, Sir Wherewell, the Grimoire, Ada from
behind, the Training Dummy, the title.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame
import pygame.gfxdraw

from engine import render

S = render.WORLD_SCALE                 # real pixels per logical pixel


def mix(a, b, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vgradient(surface, rect, stops) -> None:
    """A vertical gradient through (position 0..1, colour) stops, in real pixels."""
    x, y, w, h = rect
    for row in range(h):
        p = row / max(1, h - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= p <= p1:
                colour = mix(c0, c1, (p - p0) / max(1e-6, p1 - p0))
                break
        else:
            colour = stops[-1][1]
        pygame.draw.line(surface, colour, (x, y + row), (x + w - 1, y + row))


def _blended(surface, alpha: int, draw) -> None:
    """Translucent shapes on an image with transparency must be blended, not written: pygame's
    gfxdraw would replace the pixels (and punch a hole). Draw on a layer, then blend it."""
    if alpha >= 255 or not (surface.get_flags() & pygame.SRCALPHA):
        draw(surface)
        return
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    draw(layer)
    surface.blit(layer, (0, 0))


def disc(surface, colour, centre, radius, alpha: int = 255) -> None:
    x, y = round(centre[0]), round(centre[1])
    r = max(1, round(radius))

    def draw(target):
        pygame.gfxdraw.filled_circle(target, x, y, r, (*colour, alpha))
        pygame.gfxdraw.aacircle(target, x, y, r, (*colour, alpha))
    _blended(surface, alpha, draw)


def poly(surface, colour, points, alpha: int = 255) -> None:
    pts = [(round(px), round(py)) for px, py in points]

    def draw(target):
        pygame.gfxdraw.filled_polygon(target, pts, (*colour, alpha))
        pygame.gfxdraw.aapolygon(target, pts, (*colour, alpha))
    _blended(surface, alpha, draw)


def oval(surface, colour, rect, alpha: int = 255) -> None:
    x, y, w, h = (round(v) for v in rect)
    rx, ry = max(1, w // 2), max(1, h // 2)

    def draw(target):
        pygame.gfxdraw.filled_ellipse(target, x + w // 2, y + h // 2, rx, ry, (*colour, alpha))
        pygame.gfxdraw.aaellipse(target, x + w // 2, y + h // 2, rx, ry, (*colour, alpha))
    _blended(surface, alpha, draw)


# ------------------------------------------------------------------ the glade

@lru_cache(maxsize=8)
def glade(ground_y: int) -> pygame.Surface:
    """The Tutorial Glade at night: a deep sky, a moon with a halo, two ranges of hills, a
    pine forest, and a meadow with grass blades and flowers. Static: painted once."""
    W, H = 320 * S, 180 * S
    g = ground_y * S
    s = pygame.Surface((W, H))
    vgradient(s, (0, 0, W, g), [(0, render.INK), (0.35, render.NIGHT), (0.75, render.DUSK),
                                (1, render.VIOLET)])
    rng = _Pattern(7)
    for _ in range(140):                                  # stars of three sizes
        x, y = rng.next() % W, rng.next() % int(g * 0.7)
        size = (1, 1, 1, 2, 2, 3)[rng.next() % 6]
        colour = (render.LILAC, render.WHITE, render.SKY)[rng.next() % 3]
        disc(s, colour, (x, y), size, 200)
    mx, my = 292 * S, 14 * S                              # the moon and its halo
    for r, a in ((60, 18), (44, 30), (34, 45)):
        disc(s, render.BUTTER, (mx, my), r, a)
    disc(s, render.BUTTER, (mx, my), 26)
    disc(s, render.NIGHT, (mx + 14, my - 8), 23)          # the crescent's dark side
    for cx, cy, r in ((-10, 6, 4), (-4, 14, 3), (-16, -4, 2)):
        disc(s, render.GOLD, (mx + cx, my + cy), r, 120)  # craters
    _hills(s, g - 34 * S, render.DUSK, 0.004, 18 * S, 3)
    _hills(s, g - 18 * S, mix(render.NIGHT, render.TEAL, 0.35), 0.009, 10 * S, 11)
    _forest(s, g)
    vgradient(s, (0, g, W, H - g), [(0, render.FOREST), (0.12, mix(render.FOREST, render.GRASS, 0.35)),
                                    (1, mix(render.FOREST, render.INK, 0.35))])
    pygame.draw.line(s, mix(render.GRASS, render.MINT, 0.4), (0, g), (W, g), 3)
    rng = _Pattern(3)
    for _ in range(900):                                  # grass blades
        x = rng.next() % W
        y = g + 6 + rng.next() % max(1, H - g - 6)
        h = 6 + rng.next() % 10
        lean = (rng.next() % 7) - 3
        shade = mix(render.FOREST, render.GRASS, (rng.next() % 100) / 100)
        pygame.draw.line(s, shade, (x, y), (x + lean, y - h), 2)
    for _ in range(40):                                   # small flowers
        x = rng.next() % W
        y = g + 20 + rng.next() % max(1, H - g - 30)
        colour = (render.BUTTER, render.LILAC, render.PEACH, render.WHITE)[rng.next() % 4]
        for a in range(5):
            disc(s, colour, (x + 4 * math.cos(a * 1.26), y + 4 * math.sin(a * 1.26)), 2)
        disc(s, render.GOLD, (x, y), 2)
    return s


def _hills(s, base, colour, freq, amp, seed) -> None:
    W = s.get_width()
    pts = [(0, s.get_height())]
    for x in range(0, W + 8, 8):
        y = base - amp * (0.6 * math.sin(x * freq + seed) + 0.4 * math.sin(x * freq * 2.3 + seed * 2))
        pts.append((x, y))
    pts.append((W, s.get_height()))
    poly(s, colour, pts)


def _forest(s, g) -> None:
    rng = _Pattern(11)
    W = s.get_width()
    for layer, (dark, light, scale) in enumerate(((render.NIGHT, render.TEAL, 0.7),
                                                  (mix(render.TEAL, render.INK, 0.4), render.TEAL, 1.0))):
        x = -20
        while x < W + 20:
            h = (22 + rng.next() % 16) * S * scale
            w = h * 0.42
            base = g + (2 if layer else -2) * S
            pygame.draw.rect(s, render.BARK, (x - 3, base - h * 0.12, 6, h * 0.14))
            for tier in range(4):                         # tiers of needles, darker below
                ty = base - h * (0.15 + tier * 0.22)
                tw = w * (1 - tier * 0.2)
                poly(s, mix(dark, light, 0.25 + tier * 0.15),
                     [(x - tw / 2, ty), (x, ty - h * 0.32), (x + tw / 2, ty)])
            x += w * (0.55 + (rng.next() % 30) / 100)


class _Pattern:
    """A fixed pseudo-random pattern for scenery (never the battle's rng: art is static)."""

    def __init__(self, seed: int):
        self.n = seed * 2654435761 % (2 ** 32)

    def next(self) -> int:
        self.n = (self.n * 1103515245 + 12345) % (2 ** 31)
        return self.n >> 8


# ------------------------------------------------------------------ the Asterisk Slime

@lru_cache(maxsize=64)
def slime(frame: int, exhausted: bool, fainted: bool, flash: bool) -> pygame.Surface:
    """A glossy jelly dome with an asterisk heart, 48x44 logical pixels."""
    w, h = 48 * S, 44 * S
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    body, rim, dark = render.GRASS, render.FOREST, mix(render.FOREST, render.INK, 0.4)
    if flash:
        body = rim = dark = render.WHITE
    cx = w // 2
    if fainted:                                           # a puddle with crossed eyes
        oval(s, rim, (cx - 90, h - 40, 180, 34))
        oval(s, body, (cx - 84, h - 38, 168, 26))
        for ex in (cx - 30, cx + 18):
            pygame.draw.line(s, render.INK, (ex, h - 32), (ex + 12, h - 20), 4)
            pygame.draw.line(s, render.INK, (ex + 12, h - 32), (ex, h - 20), 4)
        return s
    squash = (0, 1, 2, 1)[frame % 4] + (3 if exhausted else 0)
    top = 8 + squash * 3
    bw = 76 + squash * 3
    oval(s, mix(render.INK, render.FOREST, 0.3), (cx - bw - 6, h - 22, 2 * bw + 12, 20), 160)   # shadow
    rect = (cx - bw, top, 2 * bw, h - top - 10)
    oval(s, dark, (rect[0] - 4, rect[1] - 4, rect[2] + 8, rect[3] + 8))
    oval(s, rim, rect)
    inner = (rect[0] + 6, rect[1] + 4, rect[2] - 12, rect[3] - 14)
    for i in range(24):                                   # volume: lighter towards the top
        t = i / 23
        x, y, w2, h2 = (round(inner[0] + i * 1.6), round(inner[1] + i * 0.6),
                        round(inner[2] - i * 3.2), round(inner[3] - i * 2.2))
        if w2 > 4 and h2 > 4:                             # filled only: no ring lines
            pygame.gfxdraw.filled_ellipse(s, x + w2 // 2, y + h2 // 2, w2 // 2, h2 // 2,
                                          (*mix(rim, body, 0.35 + 0.65 * t), 255))
    if flash:
        return s
    oval(s, render.MINT, (cx - bw * 0.55, top + 14, 30, 18), 200)        # shine
    disc(s, render.WHITE, (cx - bw * 0.45, top + 18), 5, 230)
    heart_y = top + (h - top) * 0.58                      # the asterisk heart, glowing
    disc(s, render.GOLD, (cx, heart_y), 22, 60)
    for a in range(3):
        ang = a * math.pi / 3
        dx, dy = 16 * math.cos(ang), 16 * math.sin(ang)
        pygame.draw.line(s, render.GOLD, (cx - dx, heart_y - dy), (cx + dx, heart_y + dy), 7)
    disc(s, render.BUTTER, (cx, heart_y), 5)
    eye_y = top + (h - top) * 0.32
    for ex in (cx - 28, cx + 28):                          # eyes: white, pupil, a spark
        if exhausted:
            pygame.draw.line(s, render.INK, (ex - 9, eye_y + 2), (ex + 9, eye_y + 2), 4)
            continue
        oval(s, render.WHITE, (ex - 10, eye_y - 12, 20, 24))
        disc(s, render.INK, (ex + 2, eye_y + 2), 7)
        disc(s, render.WHITE, (ex + 4, eye_y - 2), 2)
    if exhausted:                                          # a drop of sweat
        poly(s, render.SKY, [(cx + bw * 0.7, top + 20), (cx + bw * 0.62, top + 36),
                             (cx + bw * 0.78, top + 36)])
    else:
        pygame.draw.arc(s, render.INK, (cx - 12, eye_y + 10, 24, 14), math.pi * 1.1,
                        math.pi * 1.9, 3)                  # a small smile
    return s


# ------------------------------------------------------------------ Sir Wherewell

@lru_cache(maxsize=64)
def knight(frame: int, flash: bool, ward: bool, walking: bool) -> pygame.Surface:
    """An armoured knight seen from the side-front: plumed helm, filter shield, sword."""
    w, h = 44 * S, 60 * S
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    steel, light, dark = render.GREY, render.WHITE, render.SLATE
    cloth = render.WINE
    if flash:
        steel = light = dark = cloth = render.WHITE
    bob = (0, 1, 0, 1)[frame % 4] * (2 if walking else 1)
    cx = w // 2
    if ward and not flash:                                 # the Ward of Relevance
        for r, a in ((96, 20), (84, 36), (74, 50)):
            pygame.draw.circle(s, render.AQUA + (a,), (cx, h // 2), r, 4)
    oval(s, mix(render.INK, render.SLATE, 0.3), (cx - 50, h - 18, 100, 16), 150)
    legs = [(cx - 22, h - 70 + bob), (cx + 4, h - 70 - bob)]
    for lx, ly in legs:                                    # greaves and boots
        pygame.draw.rect(s, dark, (lx, ly, 18, 56), border_radius=6)
        pygame.draw.rect(s, steel, (lx + 3, ly + 3, 12, 30), border_radius=4)
        pygame.draw.rect(s, render.INK, (lx - 2, h - 20, 24, 10), border_radius=4)
    torso = pygame.Rect(cx - 32, 70 + bob, 64, 86)
    pygame.draw.rect(s, cloth, torso.inflate(8, 10), border_radius=12)   # tabard
    pygame.draw.rect(s, dark, torso, border_radius=14)
    pygame.draw.rect(s, steel, torso.inflate(-10, -10), border_radius=12)
    pygame.draw.line(s, light, (torso.x + 14, torso.y + 12), (torso.x + 14, torso.bottom - 16), 3)
    pygame.draw.rect(s, render.GOLD, (torso.x, torso.y + 52, torso.w, 8))   # belt
    helm = pygame.Rect(cx - 26, 18 + bob, 52, 56)
    pygame.draw.ellipse(s, dark, helm)
    pygame.draw.ellipse(s, steel, helm.inflate(-8, -8))
    pygame.draw.rect(s, render.INK, (helm.x + 10, helm.y + 24, helm.w - 20, 6))   # visor slit
    pygame.draw.line(s, light, (helm.x + 14, helm.y + 10), (helm.x + 20, helm.y + 6), 3)
    for i in range(6):                                     # the plume
        poly(s, mix(cloth, render.RED, i / 5),
             [(cx + i * 3, helm.y + 4), (cx - 20 + i * 8, helm.y - 24 + i * 2), (cx + 6 + i * 3, helm.y + 2)])
    shield = [(cx - 62, 92 + bob), (cx - 22, 92 + bob), (cx - 22, 140 + bob), (cx - 42, 160 + bob),
              (cx - 62, 140 + bob)]
    poly(s, dark, shield)
    poly(s, render.NAVY if not flash else light,
         [(cx - 58, 96 + bob), (cx - 26, 96 + bob), (cx - 26, 138 + bob), (cx - 42, 155 + bob),
          (cx - 58, 138 + bob)])
    funnel = [(cx - 54, 104 + bob), (cx - 30, 104 + bob), (cx - 38, 122 + bob), (cx - 38, 134 + bob),
              (cx - 46, 134 + bob), (cx - 46, 122 + bob)]
    poly(s, render.GOLD if not flash else light, funnel)   # the filter emblem
    blade_x = cx + 40
    pygame.draw.rect(s, render.GOLD, (blade_x - 14, 118 + bob, 28, 6))     # guard
    pygame.draw.rect(s, light, (blade_x - 4, 30 + bob, 8, 90))             # blade
    pygame.draw.line(s, steel, (blade_x, 34 + bob), (blade_x, 116 + bob), 2)
    pygame.draw.rect(s, render.LEATHER, (blade_x - 4, 124 + bob, 8, 18))
    disc(s, render.GOLD, (blade_x, 146 + bob), 6)
    return shrink(s, 0.75)


def shrink(s: pygame.Surface, factor: float) -> pygame.Surface:
    """Drawn large for comfort, kept at the size of the old sprite."""
    return pygame.transform.smoothscale(s, (round(s.get_width() * factor),
                                            round(s.get_height() * factor)))


# ------------------------------------------------------------------ the Grimoire

@lru_cache(maxsize=32)
def book(frame: int, speaking: bool) -> pygame.Surface:
    """The floating Grimoire, open: leather covers, gilded corners, lines of ink, a rune."""
    w, h = 40 * S, 26 * S
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    glow = 40 + 20 * math.sin(frame * 0.8)
    oval(s, render.LILAC, (8, 8, w - 16, h - 16), int(glow if speaking else 18))
    cover = render.LEATHER
    for side in (-1, 1):
        x0 = w // 2
        pts = [(x0, 18), (x0 + side * (w // 2 - 12), 12), (x0 + side * (w // 2 - 8), h - 22), (x0, h - 14)]
        poly(s, cover, pts)
        page = [(x0, 24), (x0 + side * (w // 2 - 20), 18), (x0 + side * (w // 2 - 16), h - 30), (x0, h - 22)]
        poly(s, render.CREAM, page)
        for line in range(5):                              # lines of ink
            y = 34 + line * 12
            xa, xb = x0 + side * 10, x0 + side * (w // 2 - 26)
            pygame.draw.line(s, mix(render.SAND, render.LEATHER, 0.3), (xa, y), (xb, y - 3 * side * 0), 2)
        disc(s, render.GOLD, (x0 + side * (w // 2 - 10), 14), 4)
        disc(s, render.GOLD, (x0 + side * (w // 2 - 7), h - 22), 4)
    pygame.draw.line(s, render.BARK, (w // 2, 18), (w // 2, h - 14), 3)    # the spine
    if speaking:
        disc(s, render.BUTTER, (w // 2 + 30, 44), 5, 220)
    return shrink(s, 0.8)


# ------------------------------------------------------------------ Ada, from behind

@lru_cache(maxsize=4)
def ada_back(flash: bool = False) -> pygame.Surface:
    """The protagonist from behind, 20x41 logical pixels (the grid of the battle sprite, so
    the row-by-row animation of AdaAnimator applies): pointed hat with a band and a curl,
    long auburn hair in strands, a violet robe with folds and gold trim, boots, hands."""
    w, h = 20 * S, 41 * S
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    robe, robe_d, trim = render.VIOLET, render.DUSK, render.GOLD
    hair, hair_d = render.BRICK, render.RUST
    hat, hat_d = render.VIOLET, render.DUSK
    skin = render.PEACH
    if flash:
        robe = robe_d = trim = hair = hair_d = hat = hat_d = skin = render.WHITE
    poly(s, robe_d, [(cx - 22, 62), (cx + 22, 62), (cx + 34, h - 14), (cx - 34, h - 14)])   # robe
    poly(s, robe, [(cx - 18, 64), (cx + 18, 64), (cx + 28, h - 16), (cx - 28, h - 16)])
    for fx in (-16, -4, 8, 18):                            # folds
        pygame.draw.line(s, robe_d, (cx + fx * 0.5, 80), (cx + fx, h - 18), 2)
    pygame.draw.rect(s, trim, (cx - 30, h - 20, 60, 5), border_radius=2)   # hem
    pygame.draw.rect(s, trim, (cx - 18, 92, 36, 4))                         # belt
    for side in (-1, 1):                                   # sleeves and hands
        poly(s, robe_d, [(cx + side * 16, 64), (cx + side * 26, 70), (cx + side * 30, 112),
                         (cx + side * 20, 112)])
        disc(s, skin, (cx + side * 26, 116), 5)
    for bx in (-12, 4):                                    # boots
        pygame.draw.rect(s, render.BARK, (cx + bx, h - 14, 10, 12), border_radius=3)
    head = (cx, 50)
    disc(s, hair_d, head, 20)                              # hair from behind
    poly(s, hair_d, [(cx - 20, 50), (cx + 20, 50), (cx + 16, 104), (cx - 16, 104)])
    for i, hx in enumerate(range(-16, 18, 5)):             # strands
        pygame.draw.line(s, hair if i % 2 else mix(hair, render.PEACH, 0.2),
                         (cx + hx * 0.6, 40), (cx + hx, 102), 3)
    poly(s, hat_d, [(cx - 34, 36), (cx + 34, 36), (cx + 28, 44), (cx - 28, 44)])     # brim
    poly(s, hat, [(cx - 20, 38), (cx + 20, 38), (cx + 6, 6), (cx + 20, 0), (cx + 2, 4)])   # cone
    pygame.draw.line(s, trim, (cx - 19, 34), (cx + 19, 34), 4)                       # band
    disc(s, render.BUTTER, (cx + 20, 0), 3)                # the curl's star
    return s


# ------------------------------------------------------------------ the title

@lru_cache(maxsize=4)
def title(text: str) -> pygame.Surface:
    """SQL WITCH in big, rounded, gilded letters with an ink outline (HD, any language)."""
    font = pygame.font.Font(str(render.fonts.HD_FONT[True]), 34 * S // 2)
    face = font.render(text, True, render.BUTTER)
    w, h = face.get_width() + 16, face.get_height() + 16
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    outline = font.render(text, True, render.INK)
    for dx in range(-6, 7, 3):
        for dy in range(-6, 7, 3):
            s.blit(outline, (8 + dx, 8 + dy + 4))
    shade = font.render(text, True, render.AMBER)
    s.blit(shade, (8, 12))
    s.blit(face, (8, 8))
    shine = pygame.Surface(face.get_size(), pygame.SRCALPHA)
    vgradient(shine, (0, 0, face.get_width(), face.get_height() // 2),
              [(0, render.WHITE), (1, render.BUTTER)])
    shine.blit(face, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(shine, (8, 8))
    return s


# ------------------------------------------------------------------ the Filter Keep

@lru_cache(maxsize=4)
def keep(ground_y: int) -> pygame.Surface:
    """The courtyard of the Filter Keep at dusk, static: a dusk sky, a stone wall with
    shaded blocks and battlements, an arched gate with its portcullis, banners with the
    filter funnel, torch brackets, and a flagstone floor. The flames are drawn per frame."""
    W, H = 320 * S, 180 * S
    g = ground_y * S
    s = pygame.Surface((W, H))
    vgradient(s, (0, 0, W, 14 * S), [(0, render.DUSK), (1, render.NIGHT)])
    top = 14 * S
    vgradient(s, (0, top, W, g - top), [(0, mix(render.SLATE, render.GREY, 0.35)), (1, render.SLATE)])
    rng = _Pattern(5)
    for row, y in enumerate(range(top + 4, g, 6 * S)):        # stone blocks, each its own shade
        offset = (row % 2) * 6 * S
        for x in range(-offset, W, 12 * S):
            shade = mix(render.SLATE, render.GREY, (rng.next() % 40) / 100)
            pygame.draw.rect(s, shade, (x + 2, y + 2, 12 * S - 4, 6 * S - 4), border_radius=3)
            pygame.draw.line(s, mix(shade, render.WHITE, 0.25), (x + 4, y + 3), (x + 12 * S - 6, y + 3), 2)
            pygame.draw.line(s, mix(render.SLATE, render.INK, 0.5), (x + 2, y + 6 * S - 3),
                             (x + 12 * S - 3, y + 6 * S - 3), 2)
    for x in range(0, W, 12 * S):                            # battlements
        pygame.draw.rect(s, render.SLATE, (x, top - 6 * S, 7 * S, 6 * S), border_radius=4)
        pygame.draw.line(s, mix(render.SLATE, render.WHITE, 0.3), (x + 4, top - 6 * S + 3),
                         (x + 7 * S - 4, top - 6 * S + 3), 3)
    gx, gw, gh = 232 * S, 40 * S, 34 * S                     # the gate
    gy = g - gh
    poly(s, mix(render.BARK, render.INK, 0.4), [(gx - 8, g), (gx - 8, gy), (gx + gw + 8, gy), (gx + gw + 8, g)])
    disc(s, mix(render.BARK, render.INK, 0.4), (gx + gw / 2, gy), gw / 2 + 8)
    vgradient(s, (gx, gy, gw, gh), [(0, render.INK), (1, render.BARK)])
    disc(s, render.INK, (gx + gw / 2, gy), gw / 2)
    for x in range(gx + 10, gx + gw, 6 * S):                  # the portcullis
        pygame.draw.line(s, mix(render.GREY, render.INK, 0.4), (x, gy - gw // 2 + 12), (x, g), 5)
    for y in range(gy - gw // 3, g, 6 * S):
        pygame.draw.line(s, mix(render.GREY, render.INK, 0.5), (gx + 4, y), (gx + gw - 4, y), 3)
    for bx in (60, 120, 300):                                 # banners with folds
        x0, y0 = bx * S - 6 * S, top + 2 * S
        vgradient(s, (x0, y0, 12 * S, 22 * S), [(0, render.BLUE), (1, render.NAVY)])
        poly(s, render.NAVY, [(x0, y0 + 22 * S), (bx * S, y0 + 27 * S), (x0 + 12 * S, y0 + 22 * S)])
        for fx in (x0 + 12, x0 + 30):
            pygame.draw.line(s, mix(render.NAVY, render.INK, 0.4), (fx, y0 + 4), (fx, y0 + 22 * S - 6), 3)
        poly(s, render.WHITE, [(bx * S - 16, y0 + 24), (bx * S + 16, y0 + 24), (bx * S, y0 + 46)])
        pygame.draw.rect(s, render.WHITE, (bx * S - 2, y0 + 46, 5, 18))
        pygame.draw.rect(s, render.GOLD, (x0 - 4, y0 - 6, 12 * S + 8, 6), border_radius=3)
    for tx in (90, 210):                                      # torch brackets
        pygame.draw.rect(s, render.BARK, (tx * S - 4, (top // S + 20) * S, 12, 8 * S), border_radius=3)
    vgradient(s, (0, g, W, H - g), [(0, mix(render.GREY, render.SLATE, 0.3)), (1, render.SLATE)])
    for row, y in enumerate(range(g, H, 8 * S)):              # flagstones
        pygame.draw.line(s, mix(render.SLATE, render.INK, 0.4), (0, y), (W, y), 3)
        for x in range((row % 2) * 10 * S, W, 20 * S):
            pygame.draw.line(s, mix(render.SLATE, render.INK, 0.4), (x, y), (x, y + 8 * S), 3)
    return s


@lru_cache(maxsize=16)
def flame(frame: int) -> pygame.Surface:
    """A torch flame with its glow, 16x16 logical pixels, flickering over 4 frames."""
    w = h = 16 * S
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    sway = (0, 2, -2, 1)[frame % 4]
    disc(s, render.GOLD, (w / 2, h * 0.62), 26 + frame % 2 * 3, 50)
    poly(s, render.GOLD, [(w / 2 - 9, h * 0.75), (w / 2 + 9, h * 0.75), (w / 2 + sway, h * 0.25)])
    poly(s, render.BUTTER, [(w / 2 - 4, h * 0.74), (w / 2 + 4, h * 0.74), (w / 2 + sway / 2, h * 0.42)])
    return s


# ------------------------------------------------------------------ the Training Dummy

@lru_cache(maxsize=16)
def dummy(flash: bool) -> pygame.Surface:
    """A straw-stuffed sack on a post with a painted target and stitched eyes, 32x40 logical."""
    w, h = 32 * S, 40 * S
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    straw, sack, wood, rope = ((render.WHITE,) * 4 if flash else
                               (render.BUTTER, render.SAND, render.BARK, render.LEATHER))
    cx = w // 2
    oval(s, mix(render.INK, render.FOREST, 0.3), (cx - 34, h - 14, 68, 12), 150)
    pygame.draw.rect(s, wood, (cx - 5, 80, 10, h - 88), border_radius=3)        # the post
    pygame.draw.rect(s, wood, (cx - 26, h - 12, 52, 8), border_radius=3)
    pygame.draw.rect(s, rope, (cx - 54, 56, 108, 10), border_radius=4)          # the arms
    for side in (-1, 1):                                                       # straw hands
        for i in range(5):
            pygame.draw.line(s, straw, (cx + side * 54, 60), (cx + side * (58 + i * 2), 46 + i * 5), 3)
    oval(s, mix(sack, render.LEATHER, 0.4), (cx - 38, 46, 76, 74))              # the sack
    oval(s, sack, (cx - 34, 48, 68, 68))
    for i in range(6):                                                         # stitches
        pygame.draw.line(s, rope, (cx - 30 + i * 12, 112), (cx - 26 + i * 12, 118), 2)
    if not flash:
        for r, c in ((18, render.RED), (12, render.CREAM), (6, render.RED)):  # the target
            disc(s, c, (cx, 82), r)
    pygame.draw.line(s, rope, (cx - 30, 100), (cx + 30, 100), 4)                # the belt
    disc(s, mix(straw, render.AMBER, 0.4), (cx, 30), 24)                        # the head
    disc(s, straw, (cx, 28), 21)
    for i in range(7):                                                         # straw on top
        pygame.draw.line(s, render.AMBER if not flash else straw, (cx - 12 + i * 4, 10),
                         (cx - 16 + i * 6, -2 + (i % 2) * 4), 3)
    if not flash:
        for ex in (cx - 9, cx + 9):                                            # stitched eyes
            pygame.draw.line(s, render.INK, (ex - 4, 22), (ex + 4, 30), 3)
            pygame.draw.line(s, render.INK, (ex + 4, 22), (ex - 4, 30), 3)
        pygame.draw.line(s, render.INK, (cx - 8, 40), (cx + 8, 40), 3)
    return s
