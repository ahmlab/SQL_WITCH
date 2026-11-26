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


def _layer_frame(s: dict, layer: str, option: str, p: dict) -> pygame.Surface:
    w, h = s["frame"]
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2 + p["dx"]
    top = p["dy"]
    skin, skin_d = swap(s, "skin", 0), swap(s, "skin", 1)
    hair, hair_d = swap(s, "hair", 0), swap(s, "hair", 1)
    prim, prim_d = swap(s, "primary", 0), swap(s, "primary", 1)
    sec = swap(s, "secondary", 0)
    head_y = 9 + top
    if layer == "body":
        pygame.draw.circle(img, skin, (cx, head_y), 5)                  # the back of the head
        pygame.draw.rect(img, skin_d, (cx - 1, head_y + 4, 3, 3))       # neck
        hand_y = {0: 27, 1: 19, 2: 8}[p["arms"]] + top
        for side in (-7, 6):                                            # hands
            pygame.draw.rect(img, skin, (cx + side, hand_y, 2, 2))
        for side in (-3, 1):                                            # boots
            pygame.draw.rect(img, render.BARK, (cx + side + p["step"] * (1 if side < 0 else -1),
                                                38, 3, 3))
    elif layer == "outfit":
        robe = [(cx - 4, 14 + top), (cx + 4, 14 + top), (cx + 7, 38), (cx - 7, 38)]
        if option == "coat":
            robe = [(cx - 4, 14 + top), (cx + 4, 14 + top), (cx + 5, 37), (cx - 5, 37)]
        pygame.draw.polygon(img, prim, robe)
        pygame.draw.line(img, prim_d, (cx, 15 + top), (cx, 37), 1)      # the back seam
        pygame.draw.line(img, sec, (cx - 4, 22 + top), (cx + 4, 22 + top), 1)   # belt
        if option == "robe":
            pygame.draw.line(img, sec, (cx - 7, 37), (cx + 7, 37), 1)   # hem
        else:
            pygame.draw.line(img, prim_d, (cx, 28), (cx, 37), 1)        # the coat's split
        arm_y = {0: 16, 1: 15, 2: 10}[p["arms"]] + top
        for side in (-6, 5):                                            # sleeves
            pygame.draw.rect(img, prim_d, (cx + side, arm_y, 2, 12 - 4 * p["arms"] // 2))
    elif layer == "hair":
        pygame.draw.circle(img, hair, (cx, head_y), 5)
        pygame.draw.circle(img, hair_d, (cx, head_y + 1), 4, 1)
        if option == "long":
            pygame.draw.rect(img, hair, (cx - 5, head_y, 11, 13))
            pygame.draw.line(img, hair_d, (cx, head_y + 2), (cx, head_y + 12), 1)
        elif option == "braid":
            for k in range(6):
                pygame.draw.rect(img, hair if k % 2 else hair_d, (cx - 1, head_y + 5 + 2 * k, 3, 2))
        # bob: just the head
    elif layer == "hat" and option != "none":
        brim = 7 if option == "pointed" else 9
        pygame.draw.rect(img, prim_d, (cx - brim, head_y - 5, 2 * brim + 1, 2))
        if option == "pointed":
            pygame.draw.polygon(img, prim, [(cx - 4, head_y - 5), (cx + 4, head_y - 5),
                                            (cx + 2, max(0, head_y - 13))])
        else:
            pygame.draw.rect(img, prim, (cx - 4, head_y - 9, 9, 4))
        pygame.draw.line(img, sec, (cx - 4, head_y - 6), (cx + 4, head_y - 6), 1)   # band
    elif layer == "accessory" and option != "none":
        if option == "glasses":                                         # the arms, from behind
            pygame.draw.line(img, render.INK, (cx - 5, head_y), (cx - 3, head_y), 1)
            pygame.draw.line(img, render.INK, (cx + 3, head_y), (cx + 5, head_y), 1)
        elif option == "scarf":
            pygame.draw.rect(img, sec, (cx - 4, 13 + top, 9, 2))
            pygame.draw.rect(img, sec, (cx + 2, 15 + top, 2, 5))
        elif option == "charm":
            pygame.draw.rect(img, render.SAND, (cx + 3, 23 + top, 3, 4))
            pygame.draw.line(img, render.LEATHER, (cx + 3, 23 + top), (cx + 3, 26 + top), 1)
    if p["squash"]:                                                     # folding to the ground
        squashed = pygame.transform.scale(img, (w, h - p["squash"]))
        img = pygame.Surface((w, h), pygame.SRCALPHA)
        img.blit(squashed, (0, p["squash"]))
    return img


def _portrait_frame(s: dict, layer: str, option: str, emotion: str) -> pygame.Surface:
    w, h = s["portrait_frame"]
    img = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    skin, skin_d = swap(s, "skin", 0), swap(s, "skin", 1)
    hair, hair_d = swap(s, "hair", 0), swap(s, "hair", 1)
    prim, prim_d, sec = swap(s, "primary", 0), swap(s, "primary", 1), swap(s, "secondary", 0)
    if layer == "body":
        pygame.draw.ellipse(img, skin, (cx - 7, 9, 14, 16))
        pygame.draw.rect(img, skin_d, (cx - 2, 24, 5, 3))
        eye_y = 16
        for ex in (cx - 4, cx + 3):
            if emotion == "happy":
                pygame.draw.line(img, render.INK, (ex - 1, eye_y), (ex + 1, eye_y), 1)
            else:
                pygame.draw.rect(img, render.INK, (ex, eye_y - (1 if emotion == "surprised" else 0),
                                                   1, 2 if emotion == "surprised" else 1))
        if emotion == "angry":
            pygame.draw.line(img, render.INK, (cx - 5, 13), (cx - 2, 14), 1)
            pygame.draw.line(img, render.INK, (cx + 5, 13), (cx + 2, 14), 1)
        if emotion == "sad":
            pygame.draw.line(img, render.INK, (cx - 5, 14), (cx - 2, 13), 1)
            pygame.draw.line(img, render.INK, (cx + 5, 14), (cx + 2, 13), 1)
        mouth = {"neutral": [(cx - 1, 21), (cx + 1, 21)], "happy": [(cx - 2, 20), (cx, 22), (cx + 2, 20)],
                 "sad": [(cx - 2, 22), (cx, 20), (cx + 2, 22)], "angry": [(cx - 2, 21), (cx + 2, 21)],
                 "surprised": [(cx, 21), (cx, 22)]}[emotion]
        pygame.draw.lines(img, render.WINE, False, mouth + ([mouth[-1]] if len(mouth) < 2 else []), 1)
    elif layer == "outfit":
        pygame.draw.polygon(img, prim, [(cx - 12, 32), (cx - 8, 26), (cx + 8, 26), (cx + 12, 32)])
        pygame.draw.polygon(img, sec, [(cx - 3, 26), (cx, 30), (cx + 3, 26)])
        if option == "coat":
            pygame.draw.line(img, prim_d, (cx, 30), (cx, 31), 1)
    elif layer == "hair":
        pygame.draw.rect(img, hair, (cx - 7, 8, 15, 5))                 # the fringe
        pygame.draw.line(img, hair_d, (cx - 6, 12), (cx + 6, 12), 1)
        if option in ("long", "braid"):
            pygame.draw.rect(img, hair, (cx - 9, 10, 3, 16 if option == "long" else 8))
            pygame.draw.rect(img, hair, (cx + 7, 10, 3, 16 if option == "long" else 8))
        if option == "braid":
            for k in range(4):
                pygame.draw.rect(img, hair if k % 2 else hair_d, (cx + 8, 18 + 2 * k, 2, 2))
        if option == "bob":
            pygame.draw.rect(img, hair, (cx - 8, 10, 2, 9))
            pygame.draw.rect(img, hair, (cx + 7, 10, 2, 9))
    elif layer == "hat" and option != "none":
        brim = 10 if option == "pointed" else 13
        pygame.draw.rect(img, prim_d, (cx - brim, 7, 2 * brim + 1, 2))
        if option == "pointed":
            pygame.draw.polygon(img, prim, [(cx - 6, 7), (cx + 6, 7), (cx + 3, 0)])
        else:
            pygame.draw.rect(img, prim, (cx - 6, 2, 13, 5))
        pygame.draw.line(img, sec, (cx - 6, 6), (cx + 6, 6), 1)
    elif layer == "accessory" and option != "none":
        if option == "glasses":
            for ex in (cx - 5, cx + 2):
                pygame.draw.rect(img, render.INK, (ex, 14, 4, 4), 1)
            pygame.draw.line(img, render.INK, (cx - 1, 15), (cx + 1, 15), 1)
        elif option == "scarf":
            pygame.draw.rect(img, sec, (cx - 7, 25, 15, 3))
        elif option == "charm":
            pygame.draw.rect(img, render.SAND, (cx + 7, 27, 4, 4))
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
