"""Ada comes alive: her one sprite, animated row by row (no extra frames needed).

The sprite (assets/sprites/ada_back.png, 20 x 41) is drawn one pixel row at a time, and each
row can be shifted by a pixel or two. Moving groups of rows moves parts of her:

    rows  0-5   the curled tip of the hat     rows 22-27  shoulders, sleeves, hands
    rows  0-12  the hat                       rows 28-38  the robe (gold hem at 32-34)
    rows 13-21  the hair                      rows 39-40  the feet

At 20 x 41 pixels a one-pixel move is clearly visible, so small offsets are enough:
- idle: she breathes (the upper body sinks a pixel), the hat tip sways, the hem swings;
- typing: she bows her head over the Grimoire while keys are being pressed;
- casting: a quick step towards the foe, and her hands glow in the spell's colour;
- hit: she recoils and shakes;
- low HP (the bar is red): she breathes fast and hunches;
- fainting: she sinks to her knees and topples over, and stays down.

This class only computes offsets from time and events (no pygame, no randomness): the scene
feeds it events and engine.sprites.draw_ada() draws the result.

STATUS: idle, typing, cast, hit, low HP and faint.
"""

from __future__ import annotations

import math

ROWS = 41                        # the sprite's height
HAT_TIP = range(0, 6)
HEAD = range(0, 22)              # hat and hair
UPPER = range(0, 28)             # everything above the robe
HEM = range(32, 39)
HANDS = ((3, 25), (16, 25))      # sprite pixels where her hands are

BREATH_MS, BREATH_FAST_MS = 2400, 1000
TYPING_MS = 280                  # she keeps her head bowed this long after a key
CAST_MS, HIT_MS = 480, 380
FAINT_MS = 1100                  # sinking, then toppling


class AdaAnimator:
    def __init__(self):
        self.t = 0
        self.last_key = -10 ** 6
        self.cast_at = -10 ** 6
        self.cast_colour: tuple | None = None
        self.hit_at = -10 ** 6
        self.faint_at: int | None = None
        self.low = False

    # ------------------------------------------------------------ what the scene tells it

    def update(self, dt: int) -> None:
        self.t += dt

    def typed(self) -> None:
        self.last_key = self.t

    def cast(self, colour: tuple) -> None:
        self.cast_at, self.cast_colour = self.t, colour

    def hit(self) -> None:
        self.hit_at = self.t

    def set_low(self, low: bool) -> None:
        self.low = low

    def faint(self) -> None:
        if self.faint_at is None:
            self.faint_at = self.t

    def revive(self) -> None:
        self.faint_at = None

    # ------------------------------------------------------------ what the sprite does

    @property
    def fainting(self) -> bool:
        return self.faint_at is not None

    def pose(self) -> list[tuple[int, int]]:
        """(dx, dy) in pixels for every row of the sprite, right now."""
        if self.fainting:
            return self._faint_pose()
        dx, dy = [0] * ROWS, [0] * ROWS
        t = self.t
        # Breathing: the upper body sinks one pixel for part of each breath (faster when hurt).
        period = BREATH_FAST_MS if self.low else BREATH_MS
        exhale = (t % period) < period * 0.45
        for y in UPPER:
            dy[y] += exhale
        # Hurt: a hunch, the head lower and pushed forward a little.
        if self.low:
            for y in HEAD:
                dy[y] += 1
        # Typing: the head bows over the book.
        if t - self.last_key < TYPING_MS:
            for y in HEAD:
                dy[y] += 1
        # The hat tip and the hem sway on their own slow cycles, never in step.
        tip = round(math.sin(2 * math.pi * t / 3300))
        hem = round(0.6 * math.sin(2 * math.pi * t / 2700 + 1.3))
        for y in HAT_TIP:
            dx[y] += tip
        for y in HEM:
            dx[y] += hem
        # Casting: a quick step towards the foe (right), then back.
        since = t - self.cast_at
        if 0 <= since < CAST_MS:
            step = (0, 1, 2, 2, 1)[int(5 * since / CAST_MS)]
            for y in range(ROWS - 2):                       # the feet stay planted
                dx[y] += step if y < 28 else (step + 1) // 2
        # Hit: thrown back, then shaking.
        since = t - self.hit_at
        if 0 <= since < HIT_MS:
            shove = -1 if since < 120 else (-1, 1)[(since // 50) % 2]
            for y in range(ROWS - 2):
                dx[y] += shove
            for y in HEAD:
                dy[y] += 1
        return [(min(2, max(-2, a)), min(2, max(-1, b))) for a, b in zip(dx, dy)]

    def _faint_pose(self) -> list[tuple[int, int]]:
        """Sink to the knees (the body folds towards the feet), then topple to the left."""
        p = min(1.0, (self.t - self.faint_at) / FAINT_MS)
        sink = min(1.0, p / 0.55)                           # first half: down to her knees
        fall = max(0.0, (p - 0.55) / 0.45)                  # second half: over she goes
        out = []
        for y in range(ROWS):
            height = (ROWS - 1 - y) / (ROWS - 1)            # 1 at the hat, 0 at the feet
            down = round(sink * 12 * height + fall * 10 * height ** 1.5)
            left = -round(fall * 9 * height)
            out.append((left, down))
        return out

    def glows(self) -> list[tuple[int, int, tuple, int]]:
        """(x, y, colour, size) of glowing pixels in sprite coordinates: her hands while
        she casts, pulsing in the spell's colour."""
        since = self.t - self.cast_at
        if self.fainting or self.cast_colour is None or not 0 <= since < CAST_MS + 200:
            return []
        size = 2 if (since // 60) % 2 == 0 else 1
        return [(x, y, self.cast_colour, size) for x, y in HANDS]
