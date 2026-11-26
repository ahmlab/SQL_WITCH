"""Animation: layered characters, palette swaps and the animation controller (prompt 06).

A character is a stack of layers (body, outfit, hair, hat, accessory; data/characters/<name>.json),
each a sprite sheet exported from Aseprite (json-array, --list-tags) with the same tags and frame
counts. The source art paints its recolourable parts in reserved swap colours; `palette_swap`
replaces them once, at load time, by the colours the player chose (two palette colours per part,
light and dark), through a precomputed lookup: there is no per-frame cost.

`Animator` plays the tags: frame durations from the file, a state machine (idle <-> cast -> idle;
hit interrupts anything but faint; faint is terminal), and frame events (cast frame 4 fires
"projectile") returned exactly once when the frame is entered. Given the same elapsed time it is
always in the same frame: nothing random, nothing tied to the frame rate. Guardians can use it too.

`Character` composites the layers per (tag, frame), adds a one-pixel outline in the palette's ink
(so nothing outside the 32 colours appears), and draws at whole pixels, flipped for facing, over a
cheap drop shadow. `portrait()` builds the dialogue portrait from the same choices.

Must not: touch the battle rng.

STATUS: sheet loading, palette swap, animator with events, layered character, portraits.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pygame

from engine import gfx

from engine import render

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "characters"
ASSETS = ROOT / "assets" / "characters"


@lru_cache(maxsize=None)
def spec(character: str = "witch") -> dict:
    return json.loads((DATA / f"{character}.json").read_text(encoding="utf-8"))


def palette_colour(name: str) -> tuple:
    return getattr(render, name.upper())


# ------------------------------------------------------------------ palette swap

def swap_table(look: dict, character: str = "witch") -> dict[tuple, tuple]:
    """swap colour -> chosen palette colour, for a look (the creator's choices)."""
    s = spec(character)
    chosen = {"skin": look.get("skin"), "hair": look.get("hair_colour"),
              "primary": look.get("primary"), "secondary": look.get("secondary")}
    default = s["default"]
    fallback = {"skin": default["skin"], "hair": default["hair_colour"],
                "primary": default["primary"], "secondary": default["secondary"]}
    table = {}
    for role, swaps in s["swaps"].items():
        names = s["colours"][role].get(chosen[role]) or s["colours"][role][fallback[role]]
        for swap, name in zip(swaps, names):
            table[tuple(swap)] = palette_colour(name)
    return table


def palette_swap(surface: pygame.Surface, table: dict[tuple, tuple]) -> pygame.Surface:
    """A copy of `surface` with every swap colour replaced; every other pixel untouched."""
    out = surface.copy()
    pixels = pygame.PixelArray(out)
    for old, new in table.items():
        pixels.replace(old, new)
    del pixels
    return out


# ------------------------------------------------------------------ sheets

class Sheet:
    """An Aseprite export: frames (with durations) and tags (first, last frame)."""

    def __init__(self, png: Path, table: dict | None = None):
        meta = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
        image = pygame.image.load(str(png))
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            image = image.convert_alpha()
        if table:
            image = palette_swap(image, table)
        self.frames = [image.subsurface(pygame.Rect(f["frame"]["x"], f["frame"]["y"],
                                                    f["frame"]["w"], f["frame"]["h"]))
                       for f in meta["frames"]]
        self.durations = [int(f.get("duration", 100)) for f in meta["frames"]]
        self.tags = {t["name"]: (t["from"], t["to"]) for t in meta["meta"]["frameTags"]}

    def frame(self, tag: str, i: int) -> pygame.Surface:
        first, last = self.tags[tag]
        return self.frames[min(first + i, last)]


# ------------------------------------------------------------------ the controller

class Animator:
    """Plays tags from a spec's timings. play() asks for a tag; update(ms) moves on and
    returns the events of every frame entered. Rules: a looping tag repeats; a one-shot tag
    (cast, hit) returns to idle; hit interrupts anything but faint; faint is terminal."""

    def __init__(self, tags: dict, start: str = "idle"):
        self.tags = tags
        self.tag, self.frame, self.elapsed = start, 0, 0
        self.done = False

    def play(self, tag: str) -> bool:
        """Start a tag. False when the rules refuse it (anything after faint)."""
        if tag not in self.tags or (self.tag == "faint" and tag != "faint"):
            return False
        if tag == self.tag and self.tags[tag].get("loop"):
            return True                                # already looping: keep the rhythm
        self.tag, self.frame, self.elapsed, self.done = tag, 0, 0, False
        return True

    def hit(self) -> bool:
        return self.play("hit")                        # interrupts cast, idle, walking...

    def update(self, ms: float) -> list[str]:
        events: list[str] = []
        info = self.tags[self.tag]
        self.elapsed += ms
        while not self.done and self.elapsed >= info["ms"]:
            self.elapsed -= info["ms"]
            if self.frame + 1 < info["frames"]:
                self.frame += 1
            elif info.get("loop"):
                self.frame = 0
            elif info.get("terminal"):
                self.done = True                       # faint: hold the last frame
                break
            else:                                      # a one-shot tag ends: back to idle
                self.tag, self.frame = "idle", 0
                info = self.tags["idle"]
                continue
            event = info.get("events", {}).get(str(self.frame))
            if event:
                events.append(event)
        return events


# ------------------------------------------------------------------ the layered character

def default_look(character: str = "witch") -> dict:
    return dict(spec(character)["default"])


def is_default(look: dict | None, character: str = "witch") -> bool:
    """The artist's Ada: the default look keeps her hand-made sprite in battle."""
    return not look or {**default_look(character), **look} == default_look(character)


def outline(surface: pygame.Surface, colour=render.INK, width: int = 1) -> pygame.Surface:
    """An outline `width` pixels thick around the figure, in a palette colour."""
    mask = pygame.mask.from_surface(surface)
    out = pygame.Surface((surface.get_width() + 2 * width, surface.get_height() + 2 * width),
                         pygame.SRCALPHA)
    edge = mask.to_surface(setcolor=(*colour, 255), unsetcolor=(0, 0, 0, 0))
    for dx in range(0, 2 * width + 1):
        for dy in range(0, 2 * width + 1):
            if (dx - width) ** 2 + (dy - width) ** 2 <= width * width:
                out.blit(edge, (dx, dy))
    out.blit(surface, (width, width))
    return out


class Character:
    def __init__(self, look: dict | None = None, character: str = "witch"):
        self.character = character
        self.look = {**default_look(character), **(look or {})}
        self.spec = spec(character)
        table = swap_table(self.look, character)
        base = ASSETS / character
        self.sheets = [Sheet(base / layer / f"{self.option(layer)}.png", table)
                       for layer in self.spec["layers"]]
        self.portraits = [Sheet(base / "portrait" / layer / f"{self.option(layer)}.png", table)
                          for layer in self.spec["layers"]]
        self.animator = Animator(self.spec["tags"])
        self._frames: dict[tuple, pygame.Surface] = {}

    def option(self, layer: str) -> str:
        return self.look.get(layer, self.spec["options"][layer][0])

    def frame(self, tag: str | None = None, i: int | None = None) -> pygame.Surface:
        tag = tag or self.animator.tag
        i = self.animator.frame if i is None else i
        key = (tag, i)
        if key not in self._frames:
            w, h = self.spec["frame"]
            image = pygame.Surface((w, h), pygame.SRCALPHA)
            for sheet in self.sheets:
                image.blit(sheet.frame(tag, i), (0, 0))
            self._frames[key] = outline(image, width=max(1, self.hd // 2))
        return self._frames[key]

    @property
    def hd(self) -> int:
        """Real pixels per logical pixel in this character's sheets (4 since the HD art)."""
        return int(self.spec.get("hd_scale", 1))

    def draw(self, canvas: pygame.Surface, feet: tuple[int, int], flip: bool = False,
             flash: bool = False, shadow: bool = True) -> pygame.Rect:
        image = self.frame()
        if flip:
            image = pygame.transform.flip(image, True, False)
        if flash:                                       # the white hit flash (reduced motion off)
            image = pygame.mask.from_surface(image).to_surface(setcolor=(*render.WHITE, 255),
                                                               unsetcolor=(0, 0, 0, 0))
        w, h = image.get_width() / self.hd, image.get_height() / self.hd
        x, y = feet[0] - w / 2, feet[1] - h
        if shadow:
            gfx.ellipse(canvas, render.FOREST, (feet[0] - 7, feet[1] - 3, 14, 4))
        if self.hd > 1:
            gfx.blit_hd(canvas, image, (x, y))
        else:
            canvas.blit(image, (round(x), round(y)))
        return pygame.Rect(round(x), round(y), round(w), round(h))

    def portrait(self, emotion: str = "neutral") -> pygame.Surface:
        emotions = self.spec["emotions"]
        i = emotions.index(emotion) if emotion in emotions else 0
        w, h = self.spec["portrait_frame"]
        image = pygame.Surface((w, h), pygame.SRCALPHA)
        for sheet in self.portraits:
            image.blit(sheet.frame(emotions[i], 0), (0, 0))
        return image
