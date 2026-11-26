"""The art pipeline for layered characters (docs/ART_PIPELINE.md).

    python -m tools.import_sprites placeholders     # draw every layer option by code
    python -m tools.import_sprites validate         # check every sheet and portrait
    python -m tools.import_sprites import <folder>  # copy an artist's Aseprite export, then check

Folder convention: assets/characters/<character>/<layer>/<option>.png + <option>.json (an
Aseprite export: `--format json-array --list-tags`, one frame after another) and
assets/characters/<character>/portrait/<layer>/<option>.png + .json (one frame per emotion).

The validator checks that every layer option has every tag of data/characters/<character>.json
with the same frame counts and frame size, that every portrait has every emotion, and that the
art uses only the swap colours (recoloured at load time) and the game's 32 palette colours.

The placeholder generator draws simple programmatic layers for every option (seen from behind,
like the battle sprite, plus a front portrait), so the creator and the battle work before the
artist delivers. They are honest placeholders: plain shapes, every tag, every emotion.

STATUS: placeholder generator, validator, importer.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import render  # noqa: E402

DATA = ROOT / "data" / "characters"
ASSETS = ROOT / "assets" / "characters"


def spec(character: str = "witch") -> dict:
    return json.loads((DATA / f"{character}.json").read_text(encoding="utf-8"))


def swap(spec_: dict, role: str, shade: int) -> tuple:
    return tuple(spec_["swaps"][role][shade])


# ------------------------------------------------------------------ poses

def pose(tag: str, i: int) -> dict:
    """How the figure stands in a frame: bob, lean, arms (0 down .. 2 up), squash, step."""
    p = {"dy": 0, "dx": 0, "arms": 0, "squash": 0, "step": 0}
    if tag == "idle":
        p["dy"] = (0, 0, 1, 1)[i]
    elif tag == "cast":
        p["arms"], p["dx"] = (0, 1, 2, 2, 2, 1)[i], (0, 0, -1, -1, 0, 0)[i]
    elif tag == "hit":
        p["dx"] = (2, 1, 0)[i]
    elif tag == "faint":
        p["squash"] = (0, 4, 10, 18, 26)[i]
    elif tag == "victory":
        p["dy"], p["arms"] = (0, -2, -3, -1)[i], 2
    elif tag == "rest":
        p["squash"], p["dy"] = 9, (0, 1)[i]
    elif tag.startswith("walk_"):
        p["step"], p["dy"] = (0, 1, 0, -1)[i], (0, -1, 0, -1)[i]
        p["dx"] = {"walk_left": -1, "walk_right": 1}.get(tag, 0)
    return p


Q = 4                                 # HD: four real pixels per logical pixel (D9)


def _layer_frame(s: dict, layer: str, option: str, p: dict) -> pygame.Surface:
    """One HD frame of one layer, seen from behind, 80x164 real pixels (20x41 logical).
    Hard pixels only (no anti-aliasing): every pixel is a swap or a palette colour, so the
    creator's colours replace the swap colours exactly."""
    w, h = s["frame"]
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2 + p["dx"] * Q
    top = p["dy"] * Q
    skin, skin_d = swap(s, "skin", 0), swap(s, "skin", 1)
    hair, hair_d = swap(s, "hair", 0), swap(s, "hair", 1)
    prim, prim_d = swap(s, "primary", 0), swap(s, "primary", 1)
    sec, sec_d = swap(s, "secondary", 0), swap(s, "secondary", 1)
    head_y = 36 + top
    hand_y = {0: 108, 1: 76, 2: 30}[p["arms"]] + top
    if layer == "body":
        pygame.draw.circle(img, skin, (cx, head_y), 19)                       # head
        pygame.draw.circle(img, skin_d, (cx + 4, head_y + 4), 15, 3)          # its shade
        pygame.draw.rect(img, skin_d, (cx - 5, head_y + 16, 11, 12))          # neck
        pygame.draw.rect(img, skin, (cx - 26, head_y - 2, 5, 9))              # ears
        pygame.draw.rect(img, skin, (cx + 21, head_y - 2, 5, 9))
        for side in (-1, 1):                                                 # hands
            hx = cx + side * 27 - 4
            pygame.draw.rect(img, skin, (hx, hand_y, 9, 9), border_radius=3)
            pygame.draw.line(img, skin_d, (hx + 2, hand_y + 7), (hx + 7, hand_y + 7), 2)
        for side in (-1, 1):                                                 # boots
            step = p["step"] * Q * (1 if side < 0 else -1)
            bx = cx + side * 9 - 6 + step
            pygame.draw.rect(img, render.BARK, (bx, h - 14, 13, 13), border_radius=3)
            pygame.draw.line(img, render.LEATHER, (bx + 2, h - 12), (bx + 10, h - 12), 2)
    elif layer == "outfit":
        y0 = 58 + top
        if option == "robe":
            body = [(cx - 16, y0), (cx + 16, y0), (cx + 30, h - 14), (cx - 30, h - 14)]
        else:
            body = [(cx - 16, y0), (cx + 16, y0), (cx + 22, h - 18), (cx - 22, h - 18)]
        pygame.draw.polygon(img, prim, body)
        pygame.draw.polygon(img, prim_d, body, 3)
        for fx in (-14, -5, 5, 14):                                          # folds
            pygame.draw.line(img, prim_d, (cx + fx // 3, y0 + 22), (cx + fx, body[2][1] - 4), 2)
        pygame.draw.rect(img, sec, (cx - 17, y0 + 30, 34, 5))                 # belt
        pygame.draw.rect(img, sec_d, (cx - 4, y0 + 29, 8, 7))                 # its buckle
        hem_y = body[2][1] - 4
        pygame.draw.rect(img, sec, (body[3][0], hem_y, body[2][0] - body[3][0], 4))
        if option == "coat":
            pygame.draw.line(img, prim_d, (cx, y0 + 40), (cx, hem_y), 3)      # the split
            for by in range(y0 + 8, y0 + 30, 7):
                pygame.draw.circle(img, sec, (cx - 9, by), 2)                 # buttons
        arm_top = {0: y0 + 2, 1: y0 - 4, 2: y0 - 26}[p["arms"]]
        for side in (-1, 1):                                                 # sleeves + cuffs
            sx = cx + side * 21
            sleeve = [(cx + side * 14, y0 + 2), (sx + side * 7, arm_top), (sx + side * 9, hand_y),
                      (sx - side * 3, hand_y)]
            pygame.draw.polygon(img, prim_d, sleeve)
            pygame.draw.line(img, sec, sleeve[2], sleeve[3], 3)
    elif layer == "hair":
        pygame.draw.circle(img, hair, (cx, head_y), 20)
        for hx in (-12, -6, 0, 6, 12):                                       # strands on the crown
            pygame.draw.line(img, hair_d, (cx + hx // 3, head_y - 18), (cx + hx, head_y + 16), 2)
        pygame.draw.arc(img, hair_d, (cx - 20, head_y - 20, 40, 40), 3.6, 5.8, 3)   # the nape
        if option == "long":
            pygame.draw.rect(img, hair, (cx - 20, head_y, 41, 66), border_radius=10)
            for i, hx in enumerate(range(-16, 18, 5)):                        # strands
                pygame.draw.line(img, hair_d if i % 2 else hair, (cx + hx // 2, head_y - 14),
                                 (cx + hx, head_y + 62), 2)
        elif option == "bob":
            pygame.draw.rect(img, hair, (cx - 21, head_y - 4, 43, 28), border_radius=12)
            pygame.draw.line(img, hair_d, (cx - 18, head_y + 22), (cx + 18, head_y + 22), 3)
            for hx in (-10, 0, 10):
                pygame.draw.line(img, hair_d, (cx + hx // 2, head_y - 16), (cx + hx, head_y + 20), 2)
        else:                                                                # braid
            pygame.draw.circle(img, hair_d, (cx, head_y), 20, 3)
            for k in range(9):
                bx = cx + (3 if k % 2 else -3)
                pygame.draw.ellipse(img, hair if k % 2 else hair_d, (bx - 6, head_y + 16 + k * 8, 12, 10))
            pygame.draw.rect(img, sec, (cx - 5, head_y + 86, 10, 6), border_radius=2)   # ribbon
    elif layer == "hat" and option != "none":
        brim_w = 34 if option == "pointed" else 42
        brim_y = head_y - 16
        pygame.draw.ellipse(img, prim_d, (cx - brim_w, brim_y - 5, brim_w * 2, 12))
        if option == "pointed":
            cone = [(cx - 17, brim_y), (cx + 17, brim_y), (cx + 6, brim_y - 26),
                    (cx + 16, max(0, brim_y - 34)), (cx + 2, brim_y - 30)]
            pygame.draw.polygon(img, prim, cone)
            pygame.draw.polygon(img, prim_d, cone, 2)
            pygame.draw.circle(img, sec, (cx + 16, max(2, brim_y - 34)), 3)    # a star
        else:
            pygame.draw.rect(img, prim, (cx - 17, brim_y - 18, 35, 18), border_radius=5)
            pygame.draw.rect(img, prim_d, (cx - 17, brim_y - 18, 35, 18), 2, border_radius=5)
        pygame.draw.rect(img, sec, (cx - 17, brim_y - 6, 35, 5))               # band
        pygame.draw.rect(img, sec_d, (cx - 4, brim_y - 7, 8, 7))               # buckle
    elif layer == "accessory" and option != "none":
        if option == "glasses":                                              # arms, behind
            pygame.draw.line(img, render.INK, (cx - 22, head_y - 2), (cx - 14, head_y - 2), 3)
            pygame.draw.line(img, render.INK, (cx + 14, head_y - 2), (cx + 22, head_y - 2), 3)
            pygame.draw.circle(img, render.GOLD, (cx - 22, head_y - 2), 2)
        elif option == "scarf":
            pygame.draw.rect(img, sec, (cx - 17, head_y + 18, 35, 9), border_radius=4)
            tail = [(cx + 6, head_y + 24), (cx + 16, head_y + 24), (cx + 18 + p["step"] * 2, head_y + 52),
                    (cx + 8 + p["step"] * 2, head_y + 52)]
            pygame.draw.polygon(img, sec, tail)
            for k in range(3):
                pygame.draw.line(img, sec_d, (cx + 7, head_y + 32 + k * 7), (cx + 17, head_y + 32 + k * 7), 2)
        elif option == "charm":
            bx, by = cx + 12, 90 + top
            pygame.draw.rect(img, render.SAND, (bx, by, 12, 15), border_radius=2)
            pygame.draw.rect(img, render.LEATHER, (bx, by, 3, 15))
            for gx, gy in ((bx + 9, by + 1), (bx + 9, by + 12)):
                pygame.draw.rect(img, render.GOLD, (gx, gy, 2, 2))
    if p["squash"]:                                                     # folding to the ground
        squashed = pygame.transform.scale(img, (w, h - p["squash"] * Q))
        img = pygame.Surface((w, h), pygame.SRCALPHA)
        img.blit(squashed, (0, p["squash"] * Q))
    return img


def _portrait_frame(s: dict, layer: str, option: str, emotion: str) -> pygame.Surface:
    """One HD portrait layer, 128x128, seen from the front, for one emotion."""
    w, h = s["portrait_frame"]
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    skin, skin_d = swap(s, "skin", 0), swap(s, "skin", 1)
    hair, hair_d = swap(s, "hair", 0), swap(s, "hair", 1)
    prim, prim_d = swap(s, "primary", 0), swap(s, "primary", 1)
    sec, sec_d = swap(s, "secondary", 0), swap(s, "secondary", 1)
    if layer == "body":
        pygame.draw.rect(img, skin_d, (cx - 9, 92, 19, 16))                  # neck
        pygame.draw.ellipse(img, skin, (cx - 28, 34, 56, 64))                 # face
        pygame.draw.ellipse(img, skin_d, (cx + 6, 70, 16, 10))                # cheek shade
        pygame.draw.ellipse(img, skin_d, (cx - 22, 70, 16, 10))
        eye_y = 62
        for ex in (cx - 13, cx + 13):
            if emotion == "happy":
                pygame.draw.arc(img, render.INK, (ex - 7, eye_y - 4, 14, 10), 0.2, 2.9, 3)
                continue
            tall = 14 if emotion == "surprised" else 10
            pygame.draw.ellipse(img, render.WHITE, (ex - 7, eye_y - tall // 2, 14, tall))
            pygame.draw.ellipse(img, render.INK, (ex - 3, eye_y - 4, 7, 8))
            pygame.draw.rect(img, render.WHITE, (ex, eye_y - 3, 2, 2))
        brow = {"angry": (6, -2), "sad": (-2, 6), "surprised": (-4, -4)}.get(emotion, (0, 0))
        for side in (-1, 1):
            x0, x1 = cx + side * 20, cx + side * 6
            y0 = eye_y - 12 + (brow[0] if side > 0 else brow[0])
            y1 = eye_y - 12 + (brow[1] if side > 0 else brow[1])
            pygame.draw.line(img, render.BARK, (x0, y0 if side < 0 else y1), (x1, y1 if side < 0 else y0), 3)
        pygame.draw.rect(img, skin_d, (cx - 1, 72, 3, 5))                     # nose
        mouth = {"neutral": [(cx - 6, 84), (cx + 6, 84)], "happy": [(cx - 9, 81), (cx, 88), (cx + 9, 81)],
                 "sad": [(cx - 8, 88), (cx, 83), (cx + 8, 88)], "angry": [(cx - 8, 85), (cx + 8, 83)],
                 "surprised": [(cx - 3, 82), (cx + 3, 82), (cx + 3, 89), (cx - 3, 89), (cx - 3, 82)]}[emotion]
        pygame.draw.lines(img, render.WINE, False, mouth, 3)
    elif layer == "outfit":
        shoulders = [(cx - 52, h), (cx - 40, 108), (cx + 40, 108), (cx + 52, h)]
        pygame.draw.polygon(img, prim, shoulders)
        pygame.draw.polygon(img, prim_d, shoulders, 3)
        pygame.draw.polygon(img, sec, [(cx - 14, 106), (cx, 122), (cx + 14, 106)])   # collar
        if option == "coat":
            pygame.draw.line(img, prim_d, (cx, 122), (cx, h), 3)
            pygame.draw.circle(img, sec, (cx - 8, 124), 3)
    elif layer == "hair":
        pygame.draw.ellipse(img, hair, (cx - 32, 26, 64, 34))                 # crown and fringe
        for i in range(6):
            fx = cx - 26 + i * 10
            pygame.draw.polygon(img, hair, [(fx, 44), (fx + 12, 44), (fx + 4, 56 + (i % 2) * 4)])
        pygame.draw.line(img, hair_d, (cx - 24, 40), (cx + 20, 34), 3)
        if option in ("long", "braid"):
            length = 104 if option == "long" else 76
            for side in (-1, 1):
                pygame.draw.rect(img, hair, (cx + (side * 30) - (8 if side > 0 else 0), 44, 10, length - 44),
                                 border_radius=4)
        if option == "braid":
            for k in range(6):
                pygame.draw.ellipse(img, hair if k % 2 else hair_d, (cx + 26, 74 + k * 7, 10, 9))
            pygame.draw.rect(img, sec, (cx + 26, 116, 10, 5))
        if option == "bob":
            for side in (-1, 1):
                pygame.draw.rect(img, hair, (cx + side * 30 - (10 if side > 0 else 0), 40, 12, 40),
                                 border_radius=6)
    elif layer == "hat" and option != "none":
        brim_w = 46 if option == "pointed" else 58
        pygame.draw.ellipse(img, prim_d, (cx - brim_w, 22, brim_w * 2, 16))
        if option == "pointed":
            cone = [(cx - 24, 30), (cx + 24, 30), (cx + 10, 6), (cx + 26, 0), (cx + 4, 2)]
            pygame.draw.polygon(img, prim, cone)
            pygame.draw.polygon(img, prim_d, cone, 2)
        else:
            pygame.draw.rect(img, prim, (cx - 24, 6, 48, 24), border_radius=6)
        pygame.draw.rect(img, sec, (cx - 24, 24, 48, 6))
        pygame.draw.rect(img, sec_d, (cx - 5, 23, 10, 8))
    elif layer == "accessory" and option != "none":
        if option == "glasses":
            for ex in (cx - 13, cx + 13):
                pygame.draw.rect(img, render.INK, (ex - 10, 54, 20, 16), 3, border_radius=4)
            pygame.draw.line(img, render.INK, (cx - 3, 60), (cx + 3, 60), 3)
        elif option == "scarf":
            pygame.draw.rect(img, sec, (cx - 26, 100, 52, 12), border_radius=5)
            for k in range(4):
                pygame.draw.line(img, sec_d, (cx - 20 + k * 13, 101), (cx - 20 + k * 13, 110), 2)
        elif option == "charm":
            pygame.draw.rect(img, render.SAND, (cx + 28, 112, 14, 16), border_radius=2)
            pygame.draw.rect(img, render.LEATHER, (cx + 28, 112, 3, 16))
    return img


def _write_sheet(path: Path, frames: list[tuple[pygame.Surface, int]], tags: list[dict]) -> None:
    """A png with the frames side by side and its Aseprite-style JSON (json-array)."""
    w, h = frames[0][0].get_size()
    sheet = pygame.Surface((w * len(frames), h), pygame.SRCALPHA)
    for i, (frame, _) in enumerate(frames):
        sheet.blit(frame, (i * w, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(path.with_suffix(".png")))
    meta = {"frames": [{"filename": f"{path.stem} {i}", "frame": {"x": i * w, "y": 0, "w": w, "h": h},
                        "duration": ms} for i, (_, ms) in enumerate(frames)],
            "meta": {"app": "tools/import_sprites.py placeholders", "size": {"w": w * len(frames), "h": h},
                     "frameTags": tags}}
    path.with_suffix(".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def placeholders(character: str = "witch") -> int:
    s = spec(character)
    count = 0
    for layer in s["layers"]:
        for option in s["options"][layer]:
            frames, tags = [], []
            for tag, info in s["tags"].items():
                start = len(frames)
                frames += [(_layer_frame(s, layer, option, pose(tag, i)), info["ms"])
                           for i in range(info["frames"])]
                tags.append({"name": tag, "from": start, "to": len(frames) - 1,
                             "direction": "forward"})
            _write_sheet(ASSETS / character / layer / option, frames, tags)
            portraits = [(_portrait_frame(s, layer, option, e), 0) for e in s["emotions"]]
            ptags = [{"name": e, "from": i, "to": i, "direction": "forward"}
                     for i, e in enumerate(s["emotions"])]
            _write_sheet(ASSETS / character / "portrait" / layer / option, portraits, ptags)
            count += 1
    return count


# ------------------------------------------------------------------ validation

def allowed_colours(s: dict) -> set[tuple]:
    out = {tuple(c) for c in render.PALETTE}
    for pair in s["swaps"].values():
        out |= {tuple(c) for c in pair}
    return out


def _tags(meta: dict) -> dict[str, int]:
    return {t["name"]: t["to"] - t["from"] + 1 for t in meta["meta"]["frameTags"]}


def validate_sheet(png: Path, s: dict, wanted: dict[str, int], size: tuple) -> list[str]:
    problems = []
    json_path = png.with_suffix(".json")
    if not png.exists() or not json_path.exists():
        return [f"{png}: missing (.png and .json)"]
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    tags = _tags(meta)
    for tag, count in wanted.items():
        if tag not in tags:
            problems.append(f"{png.name}: no tag {tag!r}")
        elif tags[tag] != count:
            problems.append(f"{png.name}: tag {tag!r} has {tags[tag]} frames, not {count}")
    for f in meta["frames"]:
        if (f["frame"]["w"], f["frame"]["h"]) != tuple(size):
            problems.append(f"{png.name}: a frame of {f['frame']['w']}x{f['frame']['h']}, not "
                            f"{size[0]}x{size[1]}")
            break
    image = pygame.image.load(str(png))
    allowed = allowed_colours(s)
    for x in range(image.get_width()):
        for y in range(image.get_height()):
            r, g, b, a = image.get_at((x, y))
            if a and (r, g, b) not in allowed:
                problems.append(f"{png.name}: pixel ({x}, {y}) is {(r, g, b)}, not a palette or "
                                f"swap colour")
                return problems
    return problems


def validate(character: str = "witch", folder: Path | None = None) -> list[str]:
    s, base = spec(character), (folder or ASSETS / character)
    wanted = {tag: info["frames"] for tag, info in s["tags"].items()}
    emotions = {e: 1 for e in s["emotions"]}
    problems = []
    for layer in s["layers"]:
        for option in s["options"][layer]:
            problems += validate_sheet(base / layer / f"{option}.png", s, wanted, s["frame"])
            problems += validate_sheet(base / "portrait" / layer / f"{option}.png", s, emotions,
                                       s["portrait_frame"])
    return problems


def import_folder(source: Path, character: str = "witch") -> list[str]:
    problems = validate(character, source)
    if not problems:
        shutil.copytree(source, ASSETS / character, dirs_exist_ok=True)
    return problems


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    pygame.init()
    command = args[0] if args else "validate"
    if command == "placeholders":
        print(f"drew {placeholders()} layer options (sheets and portraits)")
        return 0
    problems = import_folder(Path(args[1])) if command == "import" else validate()
    print("\n".join(problems) or "every layer has every tag, frame and colour it needs")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
