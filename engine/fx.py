"""Juice: sparks and lightning (design doc 7.3). Pure decoration, drawn on the pixel canvas.

Effects use the game's visual-only random generator (Game.vfx), never the battle's, so they
can never change what happens in a fight.

STATUS: sparks, cursor lightning, spell bolts, typing streak glow.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from engine import render

SPARK_COLOURS = (render.BUTTER, render.GOLD, render.LILAC, render.SKY, render.WHITE)


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    colour: tuple
    life: int                 # ms left
    age: int = 0


@dataclass
class Bolt:
    """A jagged line of light. Its zigzag is re-rolled every few frames, so it crackles."""
    start: tuple[float, float]
    end: tuple[float, float]
    life: int
    jitter: float
    core: tuple = render.WHITE
    glow: tuple = render.LAVENDER
    segments: int = 5
    age: int = 0
    points: list[tuple[int, int]] = field(default_factory=list)


class Effects:
    """All live sparks and bolts. update() every tick, draw() every frame."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.sparks: list[Spark] = []
        self.bolts: list[Bolt] = []

    # ------------------------------------------------------------ spawning

    def burst(self, x: float, y: float, count: int = 5, speed: float = 40,
              colours=SPARK_COLOURS, life: int = 320) -> None:
        for _ in range(count):
            angle = self.rng.uniform(-math.pi, 0)            # mostly upwards
            v = self.rng.uniform(0.4, 1.0) * speed
            self.sparks.append(Spark(x, y, math.cos(angle) * v, math.sin(angle) * v,
                                     self.rng.choice(colours),
                                     self.rng.randint(life // 2, life)))

    def zap(self, x: float, y: float, height: int = 12) -> None:
        """The little lightning on every key: from the letter, up into the page."""
        top = (x + self.rng.uniform(-4, 4), y - height - self.rng.uniform(0, 5))
        self.bolts.append(Bolt((x, y), top, life=110, jitter=2.5, core=render.BUTTER,
                               glow=render.LAVENDER, segments=3))

    def bolt(self, start: tuple[float, float], end: tuple[float, float],
             colour: tuple = render.LILAC, life: int = 260) -> None:
        """A spell bolt flying from caster to target."""
        self.bolts.append(Bolt(start, end, life=life, jitter=6, core=render.WHITE,
                               glow=colour, segments=8))
        self.burst(*end, count=10, speed=70)

    # ------------------------------------------------------------ time

    def update(self, dt: int) -> None:
        for s in self.sparks:
            s.age += dt
            s.x += s.vx * dt / 1000
            s.y += s.vy * dt / 1000
            s.vy += 140 * dt / 1000                          # a little gravity
        self.sparks = [s for s in self.sparks if s.age < s.life]
        for b in self.bolts:
            b.age += dt
            if not b.points or b.age % 48 < dt:              # re-roll the zigzag: crackle
                b.points = self._zigzag(b)
        self.bolts = [b for b in self.bolts if b.age < b.life]

    def _zigzag(self, bolt: Bolt) -> list[tuple[int, int]]:
        (x0, y0), (x1, y1) = bolt.start, bolt.end
        points = [(x0, y0)]
        for i in range(1, bolt.segments):
            t = i / bolt.segments
            points.append((x0 + (x1 - x0) * t + self.rng.uniform(-bolt.jitter, bolt.jitter),
                           y0 + (y1 - y0) * t + self.rng.uniform(-bolt.jitter, bolt.jitter)))
        points.append((x1, y1))
        return [(render.snap(x), render.snap(y)) for x, y in points]

    def busy(self) -> bool:
        return bool(self.sparks or self.bolts)

    # ------------------------------------------------------------ drawing

    def draw(self, canvas: pygame.Surface) -> None:
        for b in self.bolts:
            if len(b.points) < 2 or (b.age // 32) % 3 == 2:   # flicker
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1)):         # glow first, then the core
                pygame.draw.lines(canvas, b.glow, False,
                                  [(x + dx, y + dy) for x, y in b.points])
            pygame.draw.lines(canvas, b.core, False, b.points)
        for s in self.sparks:
            colour = s.colour if s.age < s.life * 0.6 else render.GREY
            canvas.set_at((render.snap(s.x), render.snap(s.y)), colour)


class Streak:
    """How hard the player is typing right now: keys in the last second, for the page glow."""
    WINDOW_MS = 1000

    def __init__(self):
        self.times: list[int] = []

    def hit(self, now: int) -> None:
        self.times.append(now)

    def level(self, now: int) -> float:
        """0.0 (idle) to 1.0 (typing fast: about 8 keys per second or more)."""
        self.times = [t for t in self.times if now - t < self.WINDOW_MS]
        return min(1.0, len(self.times) / 8)
