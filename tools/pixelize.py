"""Turn an AI-generated "pixel art" image into a real pixel-art sprite at game size.

    python -m tools.pixelize INPUT OUTPUT [--block 15] [--merge 18] [--palette]

Image generators paint pixel art at a large size with fuzzy, slightly irregular blocks. This
tool (docs/SPRITES.md, steps 2 and 3):
1. finds the block grid (block size and offset) by lining it up with the colour edges;
2. reads each block from its centre only (the edges are where the blur and noise are), using
   the median colour, and keeps it only if most of the centre is opaque;
3. crops to the figure, and merges shades closer than --merge so the sprite has clean flat
   colours; --palette instead snaps every colour to the game's 32-colour palette.
Needs pygame and numpy (numpy comes with the evaluation packages in requirements.txt).
"""

from __future__ import annotations

import argparse
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np  # noqa: E402
import pygame  # noqa: E402


def load_rgba(path: str) -> np.ndarray:
    surface = pygame.image.load(path)
    if surface.get_bitsize() < 32:
        surface = surface.convert_alpha() if pygame.display.get_init() else surface
    rgb = pygame.surfarray.array3d(surface).transpose(1, 0, 2).astype(int)
    try:
        alpha = pygame.surfarray.array_alpha(surface).T.astype(int)
    except ValueError:
        alpha = np.full(rgb.shape[:2], 255)
    return np.dstack([rgb, alpha])


def find_grid(img: np.ndarray, axis: int, low: float, high: float) -> tuple[float, float]:
    """Block size and offset along one axis that best match the colour edges."""
    rgb = img[:, :, :3] * (img[:, :, 3:4] > 128)
    jumps = np.abs(np.diff(rgb, axis=axis)).sum(axis=2) > 60
    edges = (np.nonzero(jumps)[1] if axis == 1 else np.nonzero(jumps)[0]).astype(float) + 1
    best = (-1.0, low, 0.0)
    for block in np.arange(low, high, 0.01):
        r = edges % block
        # The offset is the circular mean of where edges fall inside a block.
        angle = np.angle(np.exp(2j * np.pi * r / block).mean())
        phase = (angle / (2 * np.pi) * block) % block
        d = (edges - phase) % block
        score = (np.minimum(d, block - d) < 1.5).mean()
        if score > best[0]:
            best = (score, block, phase)
    return best[1], best[2]


def sample(img: np.ndarray, bx: float, px: float, by: float, py: float) -> np.ndarray:
    """One RGBA value per block, read from the middle half of the block."""
    h, w = img.shape[:2]
    cols, rows = int((w - px) // bx), int((h - py) // by)
    out = np.zeros((rows, cols, 4), dtype=int)
    for r in range(rows):
        y0, y1 = int(py + (r + 0.25) * by), int(py + (r + 0.75) * by)
        for c in range(cols):
            x0, x1 = int(px + (c + 0.25) * bx), int(px + (c + 0.75) * bx)
            cell = img[y0:y1 + 1, x0:x1 + 1].reshape(-1, 4)
            solid = cell[cell[:, 3] > 128]
            if len(solid) * 2 > len(cell):                 # mostly opaque: keep it
                out[r, c, :3] = np.median(solid[:, :3], axis=0)
                out[r, c, 3] = 255
    return out


def crop(sprite: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(sprite[:, :, 3])
    return sprite[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def merge_shades(sprite: np.ndarray, distance: float) -> np.ndarray:
    """Greedy merge of near-identical colours (most frequent first): flat, clean shading."""
    solid = sprite[:, :, 3] > 0
    colours, counts = np.unique(sprite[solid][:, :3], axis=0, return_counts=True)
    kept: list[np.ndarray] = []
    mapping = {}
    for i in np.argsort(-counts):
        c = colours[i]
        near = [k for k in kept if np.linalg.norm(k - c) < distance]
        mapping[tuple(c)] = near[0] if near else c
        if not near:
            kept.append(c)
    out = sprite.copy()
    for y, x in zip(*np.nonzero(solid)):
        out[y, x, :3] = mapping[tuple(sprite[y, x, :3])]
    return out


def snap_to_palette(sprite: np.ndarray) -> np.ndarray:
    from engine.render import PALETTE
    palette = np.array(PALETTE)
    out = sprite.copy()
    for y, x in zip(*np.nonzero(sprite[:, :, 3])):
        out[y, x, :3] = palette[np.argmin(((palette - sprite[y, x, :3]) ** 2).sum(axis=1))]
    return out


def halve(sprite: np.ndarray) -> np.ndarray:
    """Half size, kept crisp: each 2x2 group becomes its most common colour (ties go to the
    darker one), then the silhouette gets its dark outline back, because thin outlines are
    what a plain downscale loses first."""
    h, w = sprite.shape[:2]
    sprite = np.pad(sprite, ((0, h % 2), (0, w % 2), (0, 0)))
    out = np.zeros(((h + 1) // 2, (w + 1) // 2, 4), dtype=int)
    for y in range(out.shape[0]):
        for x in range(out.shape[1]):
            cell = sprite[2 * y:2 * y + 2, 2 * x:2 * x + 2].reshape(-1, 4)
            solid = [tuple(c[:3]) for c in cell if c[3]]
            if len(solid) >= 2:
                best = max(set(solid), key=lambda c: (solid.count(c), -sum(c)))
                out[y, x] = (*best, 255)
    solid = sprite[:, :, 3] > 0
    if solid.any():
        darkest = min((tuple(c) for c in sprite[solid][:, :3]), key=sum)
        mask = out[:, :, 3] > 0
        edge = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) &
                        np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
        edge[0, :] |= mask[0, :]
        edge[-1, :] |= mask[-1, :]
        edge[:, 0] |= mask[:, 0]
        edge[:, -1] |= mask[:, -1]
        out[edge, :3] = darkest
    return out


def save(sprite: np.ndarray, path: str) -> None:
    h, w = sprite.shape[:2]
    surface = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        for x in range(w):
            if sprite[y, x, 3]:
                surface.set_at((x, y), tuple(int(v) for v in sprite[y, x]))
    pygame.image.save(surface, path)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--block", type=float, default=None,
                        help="approximate block size in pixels (searched +-1.5 around it)")
    parser.add_argument("--merge", type=float, default=18.0,
                        help="merge colours closer than this (0 = keep every shade)")
    parser.add_argument("--palette", action="store_true",
                        help="snap colours to the game's 32-colour palette")
    parser.add_argument("--half", action="store_true",
                        help="half size: 2x2 blocks become one pixel, outline redrawn")
    args = parser.parse_args(argv)
    img = load_rgba(args.input)
    low, high = ((args.block - 1.5, args.block + 1.5) if args.block else (6.0, 32.0))
    bx, px = find_grid(img, 1, low, high)
    by, py = find_grid(img, 0, low, high)
    sprite = crop(sample(img, bx, px, by, py))
    if args.palette:
        sprite = snap_to_palette(sprite)
    elif args.merge > 0:
        sprite = merge_shades(sprite, args.merge)
    if args.half:
        sprite = crop(halve(sprite))
    save(sprite, args.output)
    colours = len(np.unique(sprite[sprite[:, :, 3] > 0][:, :3], axis=0))
    print(f"grid {bx:.2f} x {by:.2f} px (offset {px:.1f}, {py:.1f}) -> "
          f"sprite {sprite.shape[1]} x {sprite.shape[0]} px, {colours} colours: {args.output}")


if __name__ == "__main__":
    main()
