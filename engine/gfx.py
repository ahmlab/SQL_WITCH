"""Drawing in logical coordinates on an HD canvas (1280x720, four pixels per logical pixel).

The game lays everything out in a 320x180 grid (so the Grimoire's page is still 36 characters
wide and every rule keeps its meaning), but it draws into a canvas four times finer. These
functions have the signatures of pygame.draw and take logical coordinates, as floats if you
like: on the HD canvas they are multiplied by its scale, so a quarter of a logical pixel is one
real pixel. That is how the HD art gets its detail: `line(canvas, c, (10, 5), (12.5, 5.25),
0.25)` draws a one-pixel line between points that the old grid could not name.

On any other surface (a sprite being built, a test's plain 320x180 surface) they are exactly
pygame.draw: nothing is scaled.

`blit_hd` puts an image painted at full HD resolution (four times a logical sprite) on the
canvas at a logical position; on a plain surface it shrinks it, so tests still see it.

STATUS: rect, line, lines, polygon, circle, ellipse, arc, aaline, blit_hd; logical widths.
"""

from __future__ import annotations

import pygame


def _scale(surface) -> int:
    return getattr(surface, "scale", 1)


def _p(point, s: int, centre: bool = False) -> tuple[int, int]:
    """A logical point in real pixels; centre=True: the middle of that logical pixel (lines)."""
    off = s / 2 if centre else 0
    return round(point[0] * s + off), round(point[1] * s + off)


def _r(rect, s: int) -> pygame.Rect:
    x, y, w, h = rect if not isinstance(rect, pygame.Rect) else (rect.x, rect.y, rect.w, rect.h)
    x0, y0 = round(x * s), round(y * s)
    return pygame.Rect(x0, y0, round((x + w) * s) - x0, round((y + h) * s) - y0)


def _w(width, s: int) -> int:
    return 0 if width == 0 else max(1, round(width * s))


def _target(surface):
    """The real pygame.Surface to draw on (the HD canvas's own pixels)."""
    return surface


def rect(surface, colour, rect, width=0, border_radius=0, **kw):
    s = _scale(surface)
    if s == 1:
        return pygame.draw.rect(surface, colour, rect, width, border_radius, **kw)
    return pygame.draw.rect(surface, colour, _r(rect, s), _w(width, s),
                            _w(border_radius, s) if border_radius else 0, **kw)


def line(surface, colour, start, end, width=1):
    s = _scale(surface)
    if s == 1:
        return pygame.draw.line(surface, colour, start, end, round(width) or 1)
    w = _w(width, s)
    # A line of logical width 1 covers its logical pixels exactly: from the pixel's corner,
    # the length of the line plus one pixel. Thinner lines run through pixel centres.
    if w >= s:
        x0, y0 = start
        x1, y1 = end
        if y0 == y1:                                       # horizontal: a filled band
            left, right = min(x0, x1), max(x0, x1)
            return pygame.draw.rect(surface, colour, _r((left, y0, right - left + 1, width), s))
        if x0 == x1:                                       # vertical
            top, bottom = min(y0, y1), max(y0, y1)
            return pygame.draw.rect(surface, colour, _r((x0, top, width, bottom - top + 1), s))
    return pygame.draw.line(surface, colour, _p(start, s, True), _p(end, s, True), w)


def lines(surface, colour, closed, points, width=1):
    s = _scale(surface)
    if s == 1:
        return pygame.draw.lines(surface, colour, closed, points, round(width) or 1)
    return pygame.draw.lines(surface, colour, closed, [_p(p, s, True) for p in points],
                             _w(width, s))


def aaline(surface, colour, start, end, blend=1):
    s = _scale(surface)
    if s == 1:
        return pygame.draw.aaline(surface, colour, start, end)
    return pygame.draw.aaline(surface, colour, _p(start, s, True), _p(end, s, True))


def polygon(surface, colour, points, width=0):
    s = _scale(surface)
    if s == 1:
        return pygame.draw.polygon(surface, colour, points, round(width))
    # Logical pixels are squares: the polygon's far edges reach the far side of their pixels.
    return pygame.draw.polygon(surface, colour, [_p(p, s, True) for p in points], _w(width, s))


def circle(surface, colour, center, radius, width=0, **kw):
    s = _scale(surface)
    if s == 1:
        return pygame.draw.circle(surface, colour, center, radius, round(width), **kw)
    return pygame.draw.circle(surface, colour, _p(center, s, True),
                              max(1, round((radius + 0.5) * s)), _w(width, s), **kw)


def ellipse(surface, colour, rect, width=0):
    s = _scale(surface)
    if s == 1:
        return pygame.draw.ellipse(surface, colour, rect, round(width))
    return pygame.draw.ellipse(surface, colour, _r(rect, s), _w(width, s))


def arc(surface, colour, rect, start_angle, stop_angle, width=1):
    s = _scale(surface)
    if s == 1:
        return pygame.draw.arc(surface, colour, rect, start_angle, stop_angle, round(width) or 1)
    return pygame.draw.arc(surface, colour, _r(rect, s), start_angle, stop_angle, _w(width, s))


def blit_hd(surface, image: pygame.Surface, pos, area=None) -> pygame.Rect:
    """An image painted at HD resolution (4x a logical sprite), at a logical position."""
    s = _scale(surface)
    hd = getattr(image, "hd_scale", 4)
    if s == hd:
        return pygame.Surface.blit(surface, image, _p(pos, s), area)
    size = (max(1, image.get_width() * s // hd), max(1, image.get_height() * s // hd))
    small = pygame.transform.smoothscale(image.convert_alpha() if pygame.display.get_surface()
                                         else image, size)
    return pygame.Surface.blit(surface, small, _p(pos, s))
