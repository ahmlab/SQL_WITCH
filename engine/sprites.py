"""Sprites drawn by artists (assets/sprites/), loaded once and cached.

Pixel-art sprites are made at game size (one sprite pixel = one canvas pixel); see
docs/SPRITES.md for sizes and tools/pixelize.py to bring an AI-generated image to that size.

STATUS: Ada seen from behind, with its white hit-flash silhouette.
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


def draw_ada(canvas: pygame.Surface, feet: tuple[int, int], flash: bool = False) -> pygame.Rect:
    """Ada seen from behind, standing with her feet centred on `feet`."""
    image = sprite("ada_back", flash)
    rect = image.get_rect(midbottom=feet)
    canvas.blit(image, rect)
    return rect
