"""Sprites drawn by artists (assets/sprites/), loaded once and cached.

Pixel-art sprites are made at game size (one sprite pixel = one canvas pixel); see
docs/SPRITES.md for sizes and tools/pixelize.py to bring an AI-generated image to that size.

STATUS: Ada seen from behind, with its white hit-flash silhouette, animated row by row
(engine/ada_anim.py).
"""

from __future__ import annotations

from pathlib import Path

import pygame

SPRITE_DIR = Path(__file__).resolve().parent.parent / "assets" / "sprites"
_cache: dict[tuple[str, bool], pygame.Surface] = {}


def sprite(name: str, flash: bool = False) -> pygame.Surface:
    """assets/sprites/<name>.png. flash=True gives its white silhouette (the 1-frame hit flash
    of design doc 7.3)."""
    key = (name, flash)
    if key not in _cache:
        path = SPRITE_DIR / f"{name}.png"
        if not path.exists():
            raise FileNotFoundError(
                f"Sprite {path.name} is missing from {SPRITE_DIR}. Make it with "
                f"python -m tools.pixelize <image> {path} (see docs/SPRITES.md).")
        image = pygame.image.load(str(path))
        if flash:
            image = pygame.mask.from_surface(image).to_surface(
                setcolor=(251, 247, 239, 255), unsetcolor=(0, 0, 0, 0))
        _cache[key] = image
    return _cache[key]


def draw_ada(canvas: pygame.Surface, feet: tuple[int, int], flash: bool = False,
             anim=None) -> pygame.Rect:
    """Ada seen from behind, standing with her feet centred on `feet`. With an AdaAnimator,
    each pixel row is drawn at its own small offset (breathing, casting, fainting...)."""
    image = sprite("ada_back", flash)
    rect = image.get_rect(midbottom=feet)
    if anim is None:
        canvas.blit(image, rect)
        return rect
    width = image.get_width()
    # Bottom row first: when the body folds, the rows above are drawn over the ones below.
    for y, (dx, dy) in reversed(list(enumerate(anim.pose()))):
        canvas.blit(image, (rect.x + dx, rect.y + y + dy), (0, y, width, 1))
    for x, y, colour, size in anim.glows():
        cx, cy = rect.x + x, rect.y + y
        for ox, oy in ((-size, 0), (size, 0), (0, -size), (0, size)):   # a twinkling cross
            canvas.set_at((cx + ox, cy + oy), colour)
        canvas.set_at((cx, cy), (251, 247, 239))                        # a white-hot core
    return rect
