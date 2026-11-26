"""Story backdrops for the intro: Ada's office, the void, and the floating Grimoire.

Placeholder pixel art made of shapes in the palette, like the rest of the slice (sprites come
later, see docs/SPRITES.md). Everything is a pure function of time and a few numbers, so the
dialogue scene just says how sleepy Ada is and how long the book has existed.

STATUS: office with Ada falling asleep, the flatline void, the floating Grimoire.
"""

from __future__ import annotations

import math

import pygame

from engine import gfx

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
    gfx.rect(canvas, render.BARK, frame)
    sky = frame.inflate(-4, -4)
    gfx.rect(canvas, render.INK, sky)
    gfx.circle(canvas, render.BUTTER, (sky.right - 12, sky.y + 9), 4)
    gfx.circle(canvas, render.INK, (sky.right - 10, sky.y + 8), 3)
    x = sky.x
    for i, (w, h) in enumerate(((12, 30), (9, 42), (14, 24), (10, 36), (16, 28), (11, 46),
                                (13, 20), (8, 34))):
        if x >= sky.right:
            break
        w = min(w, sky.right - x)
        building = pygame.Rect(x, sky.bottom - h, w, h)
        gfx.rect(canvas, render.NIGHT if i % 2 else render.DUSK, building)
        for wy in range(building.y + 3, building.bottom - 2, 4):        # lit windows
            for wx in range(building.x + 2, building.right - 1, 3):
                if (wx * 7 + wy * 13 + i) % 5 == 0:
                    canvas.set_at((wx, wy), render.GOLD)
        x += w + 1
    gfx.line(canvas, render.BARK, (frame.centerx, frame.y), (frame.centerx, frame.bottom))
    gfx.line(canvas, render.BARK, (frame.x, frame.centery), (frame.right, frame.centery))


def _clock(canvas: pygame.Surface) -> None:
    centre = (142, 22)
    gfx.circle(canvas, render.INK, centre, 8)
    gfx.circle(canvas, render.CREAM, centre, 7)
    gfx.line(canvas, render.INK, centre, (centre[0] - 1, centre[1] - 6))   # 58 min
    gfx.line(canvas, render.INK, centre, (centre[0], centre[1] - 4))       # ~12 h


def _desk(canvas: pygame.Surface, t: int, steam: bool) -> None:
    gfx.rect(canvas, render.BARK, (124, 96, 182, 24))                     # front
    gfx.rect(canvas, render.LEATHER, (120, 92, 190, 4))                   # top
    # Desk lamp with its pool of light.
    gfx.rect(canvas, render.SLATE, (130, 89, 10, 3))
    gfx.line(canvas, render.SLATE, (135, 89), (138, 74))
    gfx.polygon(canvas, render.AMBER, [(132, 74), (144, 74), (141, 68), (135, 68)])
    gfx.rect(canvas, render.BUTTER, (136, 74, 4, 1))
    for x in range(126, 152, 2):
        canvas.set_at((x, 92), render.GOLD)
    # Coffee mug; it steams while Ada is still awake.
    gfx.rect(canvas, render.WHITE, (176, 84, 7, 8))
    gfx.rect(canvas, render.WHITE, (183, 86, 2, 4), 1)
    if steam:
        for i in range(2):
            for y in range(4):
                x = 178 + i * 3 + round(math.sin((t + i * 300) / 200 + y))
                canvas.set_at((x, 82 - y * 2), render.LILAC)
    gfx.rect(canvas, render.GREY, (194, 89, 26, 3))                       # keyboard
    for x in range(196, 219, 3):
        canvas.set_at((x, 90), render.INK)


def _monitor(canvas: pygame.Surface, t: int, progress: float, dead: bool) -> None:
    gfx.rect(canvas, render.SLATE, (238, 84, 6, 8))
    bezel = pygame.Rect(208, 46, 66, 40)
    gfx.rect(canvas, render.INK, bezel)
    screen = bezel.inflate(-6, -6)
    flicker = dead and (t // 110) % 3 == 0
    gfx.rect(canvas, render.INK if flicker else render.NAVY, screen)
    if flicker:
        return
    colours = (render.SKY, render.AQUA, render.LILAC, render.MINT)
    for row in range(5):                                       # lines of SQL on the screen
        y = screen.y + 3 + row * 4
        width = (17, 30, 22, 38, 14)[row]
        gfx.line(canvas, colours[row % 4], (screen.x + 3 + (row % 2) * 4, y),
                         (screen.x + 3 + width, y))
    bar = pygame.Rect(screen.x + 3, screen.bottom - 7, screen.width - 6, 4)
    gfx.rect(canvas, render.SKY, bar, 1)
    fill = round((bar.width - 2) * progress)
    gfx.rect(canvas, render.RED if dead else render.GRASS,
                     (bar.x + 1, bar.y + 1, fill, bar.height - 2))
    # The glow of the screen on the wall around it.
    for x in range(bezel.x - 3, bezel.right + 3, 2):
        canvas.set_at((x, bezel.y - 2), render.VIOLET)


def _smooth(x: float) -> float:
    """Smoothstep: 0 -> 1 with a gentle start and a gentle stop."""
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _lean(drowsy: float, t: int) -> tuple[float, float]:
    """How far Ada's torso and head lean forward (radians from upright) at this sleepiness.
    Awake she sits up; drowsy she sags and nods; asleep she folds onto her arms on the desk."""
    torso = 0.05 + 0.22 * _smooth(drowsy - 1) + 0.70 * _smooth(drowsy - 2)
    neck = 0.10 * _smooth(drowsy - 0.5) + 0.30 * _smooth(drowsy - 2)   # the head droops more
    if 1.3 < drowsy < 2.6:                                   # nodding: the head dips and jerks up
        neck += 0.25 * max(0.0, math.sin(t / 450)) * (1 - _smooth(drowsy - 2.2))
    return torso, torso + neck


HIP = (163.0, 96.0)          # where Ada sits on her chair
TORSO = 19                   # hip to shoulder
NECK = 7                     # shoulder to the centre of her head


def ada_pose(drowsy: float, t: int) -> tuple[tuple[float, float], ...]:
    """(hip, shoulder, head centre) of office Ada. The head always hangs NECK pixels from the
    shoulder, and the shoulder TORSO pixels from the hip: one body, whatever the angle."""
    torso_angle, head_angle = _lean(drowsy, t)
    shoulder = (HIP[0] + TORSO * math.sin(torso_angle), HIP[1] - TORSO * math.cos(torso_angle))
    centre = (shoulder[0] + NECK * math.sin(head_angle), shoulder[1] - NECK * math.cos(head_angle))
    return HIP, shoulder, centre


def _ada_at_desk(canvas: pygame.Surface, t: int, drowsy: float) -> None:
    """Ada from the side, facing her monitor, drawn as a tiny skeleton: the torso pivots at
    the hip and the head always sits on the neck, so she slumps as one body (never in pieces).
    drowsy: 0 awake ... 3 asleep on the desk."""
    gfx.rect(canvas, render.SLATE, (150, 66, 5, 34))                      # chair
    gfx.rect(canvas, render.SLATE, (150, 96, 26, 4))
    torso_angle, head_angle = _lean(drowsy, t)
    side = (math.cos(torso_angle), math.sin(torso_angle))                         # her front
    hip, shoulder, centre = ada_pose(drowsy, t)
    half = 7.5
    # The hips stay on the seat (the bottom edge never moves); only the back bends forward.
    torso = [(hip[0] - half, hip[1]), (hip[0] + half, hip[1]),
             (shoulder[0] + side[0] * half * 0.9, shoulder[1] + side[1] * half * 0.9),
             (shoulder[0] - side[0] * half * 0.9, shoulder[1] - side[1] * half * 0.9)]
    gfx.polygon(canvas, render.TEAL, [(render.snap(x), render.snap(y)) for x, y in torso])

    h_up = (math.sin(head_angle), -math.cos(head_angle))
    h_fwd = (math.cos(head_angle), math.sin(head_angle))

    def at(dx: float, dy: float) -> tuple[int, int]:
        """A point on the head: dx towards her face, dy towards her chin."""
        return (render.snap(centre[0] + dx * h_fwd[0] - dy * h_up[0]),
                render.snap(centre[1] + dx * h_fwd[1] - dy * h_up[1]))

    asleep = _smooth((drowsy - 2.2) / 0.8)
    if asleep > 0.5:                                          # arms folded on the desk
        elbow = (render.snap(shoulder[0] + 2), 90)
        gfx.line(canvas, render.TEAL, (render.snap(shoulder[0]), render.snap(shoulder[1])),
                         elbow, 3)
        gfx.line(canvas, render.TEAL, (elbow[0] - 2, 90), (elbow[0] + 14, 90), 3)
    else:                                                     # typing
        tap = 1 if drowsy < 1 and (t // 90) % 2 else 0
        hand = (199, 87 - tap)
        gfx.line(canvas, render.TEAL, (render.snap(shoulder[0]), render.snap(shoulder[1]) + 2),
                         hand, 3)
        gfx.rect(canvas, render.PEACH, (hand[0], hand[1] - 1, 3, 2))
    gfx.line(canvas, render.PEACH, at(0, 6), at(0, 3), 3)                 # neck
    gfx.rect(canvas, render.WHITE, (*at(2, 7), 3, 2))                     # collar
    gfx.line(canvas, render.LEATHER, at(-6, 0), at(-7, 7), 3)             # ponytail
    gfx.circle(canvas, render.LEATHER, at(0, 0), 7)                       # hair
    gfx.circle(canvas, render.PEACH, at(2, 1), 5)                         # face
    gfx.line(canvas, render.INK, at(3, -1), at(7, -1))                    # glasses
    gfx.line(canvas, render.INK, at(3, 1), at(7, 1))
    if drowsy < 0.8:
        canvas.set_at(at(5, 0), render.INK)                                       # open eye
        if (t // 900) % 4 == 0:
            canvas.set_at(at(6, -1), render.WHITE)                                # glint
    else:
        gfx.line(canvas, render.INK, at(4, 0), at(6, 0))                  # eyes closed
    if 1.8 < drowsy < 2.95:                                   # z z z (they stop with her heart)
        f = render.font()
        hx, hy = at(0, 0)
        for i in range(3):
            phase = (t / 1400 + i / 3) % 1.0
            f.draw(canvas, "z", (hx + 4 + i * 5 + phase * 6, hy - 10 - phase * 16),
                   render.LILAC if phase < 0.7 else render.GREY)


def draw_office(canvas: pygame.Surface, t: int, drowsy: float, progress: float) -> None:
    """11:58 pm at Ada's desk. The room darkens as she falls asleep; the monitor stays lit."""
    dead = drowsy >= 2.95
    gfx.rect(canvas, render.DUSK, (0, 0, 320, SCENE_H))
    gfx.rect(canvas, render.NIGHT, (0, 112, 320, 68))
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
        gfx.lines(canvas, render.GRASS, False, points)
        canvas.set_at(points[-1], render.MINT)                  # the bright tip of the trace


# ------------------------------------------------------------------ the floating book

def draw_book(canvas: pygame.Surface, centre: tuple[int, int], t: int, age: int,
              speaking: bool, ground_y: int = 110, shadow=render.FOREST) -> None:
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
    gfx.ellipse(canvas, shadow, (cx - 10, ground_y - 2, 20, 4))          # shadow
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
        gfx.polygon(canvas, render.LEATHER, [(x, y + 1) for x, y in cover])
    for page in (left, right):                               # cream pages
        gfx.polygon(canvas, render.CREAM, page)
    gfx.line(canvas, render.BARK, (cx, cy - h + 4), (cx, cy + h))       # spine
    if grow >= 1.0:
        for row in range(3):                                 # ink lines on the pages
            y = round(cy - 3 + row * 3)
            gfx.line(canvas, render.SAND, (cx - 12, y + 1), (cx - 3, y))
            gfx.line(canvas, render.SAND, (cx + 3, y), (cx + 12, y + 1))
        rune = render.GOLD if speaking and (t // 150) % 2 else render.LAVENDER
        render.font().draw(canvas, "*", (cx + 5, cy - 6), rune)
        if speaking:                                         # a page flutters as it talks
            lift = (2, 5, 8, 5)[(t // 90) % 4]
            gfx.polygon(canvas, render.PARCHMENT,
                                [(cx, cy - h + 4), (cx + 9, cy - h + 4 - lift), (cx + 9, cy + h - lift),
                                 (cx, cy + h)])


# ------------------------------------------------------------------ the Filter Keep

def draw_dummy(canvas: pygame.Surface, centre: tuple[int, int], t: int, flash: bool) -> None:
    """The Training Dummy: a straw sack on a post, a painted target, stitched eyes.
    When hit it flashes and rocks on its post."""
    cx, cy = centre
    rock = (-1, 1, -1, 0)[(t // 60) % 4] if flash else 0
    straw, sack, wood, rope = ((render.WHITE,) * 4 if flash else
                               (render.BUTTER, render.SAND, render.BARK, render.LEATHER))
    gfx.rect(canvas, wood, (cx - 1, cy + 4, 3, 13))                 # the post
    gfx.rect(canvas, wood, (cx - 6, cy + 16, 13, 2))                # its foot
    cx += rock
    gfx.rect(canvas, rope, (cx - 13, cy - 3, 27, 3))                # the arms
    for x in (cx - 14, cx + 14):                                            # straw hands
        gfx.line(canvas, straw, (x, cy - 4), (x, cy))
    gfx.ellipse(canvas, wood, (cx - 9, cy - 7, 19, 18))             # the sack
    gfx.ellipse(canvas, sack, (cx - 8, cy - 6, 17, 16))
    gfx.line(canvas, rope, (cx - 7, cy + 4), (cx + 7, cy + 4))      # the belt
    if not flash:
        gfx.circle(canvas, render.RED, (cx, cy), 4)                 # a painted target
        gfx.circle(canvas, render.CREAM, (cx, cy), 2)
        canvas.set_at((cx, cy), render.RED)
    gfx.circle(canvas, wood, (cx, cy - 11), 6)                      # the head
    gfx.circle(canvas, straw, (cx, cy - 11), 5)
    if not flash:
        for x in (cx - 2, cx + 2):                                          # stitched eyes
            canvas.set_at((x - 1, cy - 13), render.INK)
            canvas.set_at((x, cy - 12), render.INK)
        gfx.line(canvas, render.INK, (cx - 2, cy - 9), (cx + 2, cy - 9))
        for x in (cx - 3, cx + 3):                                          # straw sticking out
            canvas.set_at((x, cy - 17), render.AMBER)


def draw_keep(canvas: pygame.Surface, t: int, ground_y: int = 60) -> None:
    """The courtyard of the Filter Keep at dusk: battlements, a gate, banners and torches."""
    gfx.rect(canvas, render.NIGHT, (0, 0, 320, ground_y))
    gfx.rect(canvas, render.DUSK, (0, 0, 320, 10))
    wall_top = 14
    gfx.rect(canvas, render.SLATE, (0, wall_top, 320, ground_y - wall_top))
    for x in range(0, 320, 12):                                   # battlements
        gfx.rect(canvas, render.SLATE, (x, wall_top - 6, 7, 6))
    for row, y in enumerate(range(wall_top + 4, ground_y, 6)):    # brick courses
        gfx.line(canvas, render.DUSK, (0, y), (320, y))
        for x in range((row % 2) * 6, 320, 12):
            gfx.line(canvas, render.DUSK, (x, y - 5), (x, y - 1))
    gate = pygame.Rect(232, ground_y - 34, 40, 34)                # the gate behind his post
    gfx.rect(canvas, render.BARK, gate)
    gfx.circle(canvas, render.BARK, (gate.centerx, gate.y), gate.w // 2)
    for x in range(gate.x + 4, gate.right, 6):                    # portcullis
        gfx.line(canvas, render.INK, (x, gate.y - 12), (x, gate.bottom))
    for x in (60, 120, 300):                                      # banners with the funnel
        gfx.rect(canvas, render.NAVY, (x - 6, wall_top + 2, 12, 22))
        gfx.polygon(canvas, render.NAVY, [(x - 6, wall_top + 24), (x, wall_top + 28),
                                                  (x + 6, wall_top + 24)])
        gfx.polygon(canvas, render.WHITE, [(x - 4, wall_top + 8), (x + 4, wall_top + 8),
                                                   (x, wall_top + 14)])
        gfx.line(canvas, render.WHITE, (x, wall_top + 14), (x, wall_top + 18))
    for x in (90, 210):                                           # torches flicker
        gfx.rect(canvas, render.BARK, (x - 1, wall_top + 20, 3, 8))
        flame = render.GOLD if (t // 120 + x) % 3 else render.BUTTER
        gfx.polygon(canvas, flame, [(x - 2, wall_top + 20), (x + 3, wall_top + 20),
                                            (x + 1, wall_top + 13 - (t // 90 + x) % 2)])
    gfx.rect(canvas, render.GREY, (0, ground_y, 320, 180 - ground_y))   # flagstones
    for y in range(ground_y + 6, 180, 8):
        gfx.line(canvas, render.SLATE, (0, y), (320, y))
        for x in range((y // 8 % 2) * 10, 320, 20):
            gfx.line(canvas, render.SLATE, (x, y - 7), (x, y))


def draw_knight(canvas: pygame.Surface, centre: tuple[float, float], t: int, flash: bool,
                fainted: bool, relevance: bool, moving: bool) -> None:
    """Placeholder Sir Wherewell: blue tabard with a filter funnel, shield, sword, red plume.
    While his Ward of Relevance is up, a dashed shimmer circles him."""
    cx, cy = render.snap(centre[0]), render.snap(centre[1])
    gfx.ellipse(canvas, render.SLATE, (cx - 12, cy + 16, 24, 5))         # shadow
    if fainted:
        gfx.rect(canvas, render.GREY, (cx - 16, cy + 10, 32, 7))
        gfx.rect(canvas, render.NAVY, (cx - 8, cy + 11, 14, 5))
        return
    armour, tabard, trim = ((render.WHITE,) * 3 if flash else
                            (render.GREY, render.NAVY, render.GOLD))
    step = 2 if moving and (t // 120) % 2 else 0                                  # walking
    gfx.rect(canvas, render.SLATE, (cx - 6, cy + 8 - step, 4, 10))       # legs
    gfx.rect(canvas, render.SLATE, (cx + 2, cy + 8 - (2 - step if moving else 0), 4, 10))
    gfx.rect(canvas, armour, (cx - 8, cy - 6, 16, 15))                   # breastplate
    gfx.rect(canvas, tabard, (cx - 5, cy - 5, 10, 14))
    if not flash:
        gfx.polygon(canvas, render.WHITE, [(cx - 3, cy - 2), (cx + 3, cy - 2), (cx, cy + 2)])
        gfx.line(canvas, render.WHITE, (cx, cy + 2), (cx, cy + 5))       # the funnel
    gfx.rect(canvas, armour, (cx - 5, cy - 17, 10, 11))                  # helmet
    gfx.rect(canvas, render.INK, (cx - 3, cy - 13, 6, 1))                # visor slit
    gfx.polygon(canvas, render.WHITE if flash else render.RED,
                        [(cx - 1, cy - 17), (cx + 4, cy - 24), (cx + 2, cy - 17)])  # plume
    gfx.rect(canvas, tabard, (cx - 15, cy - 6, 7, 13))                   # shield
    gfx.rect(canvas, trim, (cx - 15, cy - 6, 7, 13), 1)
    gfx.line(canvas, render.WHITE, (cx + 10, cy - 15), (cx + 10, cy + 3))  # sword
    gfx.rect(canvas, trim, (cx + 8, cy + 2, 5, 1))
    if relevance:
        spin = t / 250
        for i in range(16):
            if (i + int(spin * 2)) % 2:
                continue
            angle = i / 16 * 2 * math.pi + spin
            canvas.set_at((render.snap(cx + math.cos(angle) * 19),
                           render.snap(cy + math.sin(angle) * 23)),
                          render.AQUA if i % 4 else render.LILAC)
