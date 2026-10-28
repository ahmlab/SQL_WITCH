"""Story backdrops for the intro: Ada's office, the void, and the floating Grimoire.

Placeholder pixel art made of shapes in the palette, like the rest of the slice (sprites come
later, see docs/SPRITES.md). Everything is a pure function of time and a few numbers, so the
dialogue scene just says how sleepy Ada is and how long the book has existed.

STATUS: office with Ada falling asleep, the flatline void, the floating Grimoire.
"""

from __future__ import annotations

import math

import pygame

from engine import render

SCENE_H = 128                       # the dialogue box covers everything below


def dim(canvas: pygame.Surface, rect: pygame.Rect, alpha: int) -> None:
    """Darken part of the canvas. Unlike render.cover, things drawn afterwards stay bright."""
    if alpha <= 0:
        return
    shade = pygame.Surface(rect.size, pygame.SRCALPHA)
    shade.fill((*render.INK, min(255, alpha)))
    canvas.blit(shade, rect.topleft)


# ------------------------------------------------------------------ the office

def _window(canvas: pygame.Surface, t: int) -> None:
    frame = pygame.Rect(16, 12, 96, 62)
    pygame.draw.rect(canvas, render.BARK, frame)
    sky = frame.inflate(-4, -4)
    pygame.draw.rect(canvas, render.INK, sky)
    pygame.draw.circle(canvas, render.BUTTER, (sky.right - 12, sky.y + 9), 4)
    pygame.draw.circle(canvas, render.INK, (sky.right - 10, sky.y + 8), 3)
    x = sky.x
    for i, (w, h) in enumerate(((12, 30), (9, 42), (14, 24), (10, 36), (16, 28), (11, 46),
                                (13, 20), (8, 34))):
        if x >= sky.right:
            break
        w = min(w, sky.right - x)
        building = pygame.Rect(x, sky.bottom - h, w, h)
        pygame.draw.rect(canvas, render.NIGHT if i % 2 else render.DUSK, building)
        for wy in range(building.y + 3, building.bottom - 2, 4):        # lit windows
            for wx in range(building.x + 2, building.right - 1, 3):
                if (wx * 7 + wy * 13 + i) % 5 == 0:
                    canvas.set_at((wx, wy), render.GOLD)
        x += w + 1
    pygame.draw.line(canvas, render.BARK, (frame.centerx, frame.y), (frame.centerx, frame.bottom))
    pygame.draw.line(canvas, render.BARK, (frame.x, frame.centery), (frame.right, frame.centery))


def _clock(canvas: pygame.Surface) -> None:
    centre = (142, 22)
    pygame.draw.circle(canvas, render.INK, centre, 8)
    pygame.draw.circle(canvas, render.CREAM, centre, 7)
    pygame.draw.line(canvas, render.INK, centre, (centre[0] - 1, centre[1] - 6))   # 58 min
    pygame.draw.line(canvas, render.INK, centre, (centre[0], centre[1] - 4))       # ~12 h


def _desk(canvas: pygame.Surface, t: int, steam: bool) -> None:
    pygame.draw.rect(canvas, render.BARK, (124, 96, 182, 24))                     # front
    pygame.draw.rect(canvas, render.LEATHER, (120, 92, 190, 4))                   # top
    # Desk lamp with its pool of light.
    pygame.draw.rect(canvas, render.SLATE, (130, 89, 10, 3))
    pygame.draw.line(canvas, render.SLATE, (135, 89), (138, 74))
    pygame.draw.polygon(canvas, render.AMBER, [(132, 74), (144, 74), (141, 68), (135, 68)])
    pygame.draw.rect(canvas, render.BUTTER, (136, 74, 4, 1))
    for x in range(126, 152, 2):
        canvas.set_at((x, 92), render.GOLD)
    # Coffee mug; it steams while Ada is still awake.
    pygame.draw.rect(canvas, render.WHITE, (176, 84, 7, 8))
    pygame.draw.rect(canvas, render.WHITE, (183, 86, 2, 4), 1)
    if steam:
        for i in range(2):
            for y in range(4):
                x = 178 + i * 3 + round(math.sin((t + i * 300) / 200 + y))
                canvas.set_at((x, 82 - y * 2), render.LILAC)
    pygame.draw.rect(canvas, render.GREY, (194, 89, 26, 3))                       # keyboard
    for x in range(196, 219, 3):
        canvas.set_at((x, 90), render.INK)


def _monitor(canvas: pygame.Surface, t: int, progress: float, dead: bool) -> None:
    pygame.draw.rect(canvas, render.SLATE, (238, 84, 6, 8))
    bezel = pygame.Rect(208, 46, 66, 40)
    pygame.draw.rect(canvas, render.INK, bezel)
    screen = bezel.inflate(-6, -6)
    flicker = dead and (t // 110) % 3 == 0
    pygame.draw.rect(canvas, render.INK if flicker else render.NAVY, screen)
    if flicker:
        return
    colours = (render.SKY, render.AQUA, render.LILAC, render.MINT)
    for row in range(5):                                       # lines of SQL on the screen
        y = screen.y + 3 + row * 4
        width = (17, 30, 22, 38, 14)[row]
        pygame.draw.line(canvas, colours[row % 4], (screen.x + 3 + (row % 2) * 4, y),
                         (screen.x + 3 + width, y))
    bar = pygame.Rect(screen.x + 3, screen.bottom - 7, screen.width - 6, 4)
    pygame.draw.rect(canvas, render.SKY, bar, 1)
    fill = round((bar.width - 2) * progress)
    pygame.draw.rect(canvas, render.RED if dead else render.GRASS,
                     (bar.x + 1, bar.y + 1, fill, bar.height - 2))
    # The glow of the screen on the wall around it.
    for x in range(bezel.x - 3, bezel.right + 3, 2):
        canvas.set_at((x, bezel.y - 2), render.VIOLET)


def _ada_at_desk(canvas: pygame.Surface, t: int, drowsy: float) -> None:
    """Ada from the side, facing her monitor. drowsy: 0 awake ... 3 asleep on the desk."""
    pygame.draw.rect(canvas, render.SLATE, (150, 66, 5, 34))                      # chair
    pygame.draw.rect(canvas, render.SLATE, (150, 96, 26, 4))
    pygame.draw.rect(canvas, render.TEAL, (156, 76, 16, 21))                      # cardigan
    pygame.draw.rect(canvas, render.WHITE, (169, 76, 3, 3))                       # collar
    # Head: upright, then sagging and nodding, then resting on the desk.
    sag = min(drowsy, 2.0)
    hx, hy = 166 + sag * 1.5, 68 + sag * 2.5
    if 1.3 < drowsy < 2.6:                                    # nodding off
        hy += 2 * max(0.0, math.sin(t / 450))
    if drowsy > 2.3:
        k = min(1.0, (drowsy - 2.3) / 0.7)                    # slide down onto the desk
        hx, hy = hx + (184 - hx) * k, hy + (86 - hy) * k
    hx, hy = render.snap(hx), render.snap(hy)
    pygame.draw.circle(canvas, render.LEATHER, (hx, hy), 7)                       # hair
    pygame.draw.rect(canvas, render.LEATHER, (hx - 9, hy, 3, 8))                  # ponytail
    pygame.draw.circle(canvas, render.PEACH, (hx + 2, hy + 1), 5)                 # face
    pygame.draw.rect(canvas, render.INK, (hx + 3, hy - 1, 5, 3), 1)               # glasses
    if drowsy < 0.8:
        canvas.set_at((hx + 5, hy), render.INK)                                   # open eye
        if (t // 900) % 4 == 0:
            canvas.set_at((hx + 6, hy - 1), render.WHITE)                         # glint
    else:
        pygame.draw.line(canvas, render.INK, (hx + 4, hy + 1), (hx + 6, hy + 1))  # closed
    # Arm: typing while awake, slumped on the desk when asleep.
    if drowsy > 2.3:
        pygame.draw.line(canvas, render.TEAL, (168, 82), (hx - 2, 90), 3)
    else:
        tap = 1 if drowsy < 1 and (t // 90) % 2 else 0
        hand = (199, 87 - tap)
        pygame.draw.line(canvas, render.TEAL, (168, 81), hand, 3)
        pygame.draw.rect(canvas, render.PEACH, (hand[0], hand[1] - 1, 3, 2))
    if 1.8 < drowsy < 2.95:                                   # z z z (they stop with her heart)
        f = render.font()
        for i in range(3):
            phase = (t / 1400 + i / 3) % 1.0
            f.draw(canvas, "z", (hx + 4 + i * 5 + phase * 6, hy - 10 - phase * 16),
                   render.LILAC if phase < 0.7 else render.GREY)


def draw_office(canvas: pygame.Surface, t: int, drowsy: float, progress: float) -> None:
    """11:58 pm at Ada's desk. The room darkens as she falls asleep; the monitor stays lit."""
    dead = drowsy >= 2.95
    pygame.draw.rect(canvas, render.DUSK, (0, 0, 320, SCENE_H))
    pygame.draw.rect(canvas, render.NIGHT, (0, 112, 320, 68))
    _window(canvas, t)
    _clock(canvas)
    _desk(canvas, t, steam=drowsy < 2)
    _ada_at_desk(canvas, t, drowsy)
    dim(canvas, pygame.Rect(0, 0, 320, 180), int(drowsy * 38))
    _monitor(canvas, t, progress, dead)


# ------------------------------------------------------------------ the void

def draw_void(canvas: pygame.Surface, t: int) -> None:
    """Black, and the last line of a heart monitor: two beats, then flat."""
    canvas.fill(render.INK)
    y, left, right = 60, 40, 280
    head = left + min(right - left, t * 0.12)                # the trace moves to the right
    points = []
    for x in range(left, int(head)):
        beat = 0
        for centre in (90, 150):                             # two weak heartbeats
            if abs(x - centre) < 6:
                beat = -(6 - abs(x - centre)) * (1 if x < centre else -0.6)
        points.append((x, y + round(beat)))
    if len(points) > 1:
        pygame.draw.lines(canvas, render.GRASS, False, points)
        canvas.set_at(points[-1], render.MINT)                  # the bright tip of the trace


# ------------------------------------------------------------------ the floating book

def draw_book(canvas: pygame.Surface, centre: tuple[int, int], t: int, age: int,
              speaking: bool, ground_y: int = 110) -> None:
    """The Grimoire: an open book floating over the grass, glowing when it talks.
    age: ms since it appeared (it pops in from a ring of sparks)."""
    if age < 0:
        return
    cx, cy = centre
    grow = min(1.0, age / 450)
    if grow < 1.0:                                           # sparks spiral in
        for i in range(10):
            angle = i / 10 * 2 * math.pi + age / 120
            r = 28 * (1 - grow) + 4
            canvas.set_at((render.snap(cx + math.cos(angle) * r),
                           render.snap(cy + math.sin(angle) * r * 0.6)),
                          render.BUTTER if i % 2 else render.LILAC)
    cy += render.snap(2 * math.sin(t / 380))                 # it floats
    pygame.draw.ellipse(canvas, render.FOREST, (cx - 10, ground_y - 2, 20, 4))   # shadow
    w, h = 16 * grow, 9 * grow
    if w < 2:
        return
    # Aura: a slow ring of light, brighter while the book is speaking.
    ring = 12 if speaking else 6
    for i in range(ring):
        angle = i / ring * 2 * math.pi + t / (300 if speaking else 900)
        canvas.set_at((render.snap(cx + math.cos(angle) * (w + 6)),
                       render.snap(cy + math.sin(angle) * (h + 5))),
                      render.BUTTER if speaking and i % 2 else render.LILAC)
    left = [(cx - w, cy - h + 2), (cx, cy - h + 4), (cx, cy + h), (cx - w, cy + h - 2)]
    right = [(cx + w, cy - h + 2), (cx, cy - h + 4), (cx, cy + h), (cx + w, cy + h - 2)]
    for cover in (left, right):                              # leather covers
        pygame.draw.polygon(canvas, render.LEATHER, [(x, y + 1) for x, y in cover])
    for page in (left, right):                               # cream pages
        pygame.draw.polygon(canvas, render.CREAM, page)
    pygame.draw.line(canvas, render.BARK, (cx, cy - h + 4), (cx, cy + h))       # spine
    if grow >= 1.0:
        for row in range(3):                                 # ink lines on the pages
            y = round(cy - 3 + row * 3)
            pygame.draw.line(canvas, render.SAND, (cx - 12, y + 1), (cx - 3, y))
            pygame.draw.line(canvas, render.SAND, (cx + 3, y), (cx + 12, y + 1))
        rune = render.GOLD if speaking and (t // 150) % 2 else render.LAVENDER
        render.font().draw(canvas, "*", (cx + 5, cy - 6), rune)
        if speaking:                                         # a page flutters as it talks
            lift = (2, 5, 8, 5)[(t // 90) % 4]
            pygame.draw.polygon(canvas, render.PARCHMENT,
                                [(cx, cy - h + 4), (cx + 9, cy - h + 4 - lift), (cx + 9, cy + h - lift),
                                 (cx, cy + h)])
