"""Story scenes from scripts: what a scene needs to know about each line.

A story scene (the intro, a guardian's arrival) plays a node of data/story/intro.script. This
module turns the script's lines into plain records the scene draws: who speaks, the text in the
current language (with its inline markup), and the stage directions read as scene properties
(backdrop, Ada's sleepiness, the floating book, who stands on stage, a sound, a portrait).

legacy() rebuilds the shape the old data/dialogue.json had, for the parts of the game that only
need text by name (result screens, the battle tip).

Never imports pygame.

STATUS: scene lines from scripts, text in the current language, the legacy dialogue shape.
"""

from __future__ import annotations

from i18n import CATALOG
from story.script import Line, ScriptRunner, get, plain

INTRO = "intro"
FLAGS = ("book", "slime", "knight")


def text_of(line: Line) -> str:
    """A line in the current language (the catalog's translation, or the script's English),
    with the player's name and gender filled in. Inline markup and the game's own
    placeholders ({rows}, {foe}...) stay for the scene to use."""
    translated = CATALOG.raw(line.key)
    return CATALOG.format(translated if translated is not None else line.text)


def speaker_name(speaker: str) -> str:
    """The name on a speaker's tag: translated for the Grimoire and the protagonist,
    as written (database names) for everyone else."""
    if not speaker:
        return ""
    shown = CATALOG.raw(f"speaker.{speaker}")
    return CATALOG.format(shown) if shown is not None else speaker


def text_of_key(key: str, default: str) -> str:
    """A script line's text by its key, in the current language."""
    translated = CATALOG.raw(key)
    return CATALOG.format(translated) if translated is not None else default


def record(line: Line) -> dict:
    """A line as the story scene reads it (the same fields data/dialogue.json had)."""
    out: dict = {"speaker": line.speaker, "key": line.key, "markup": text_of(line)}
    out["text"] = plain(out["markup"])
    for name, args in line.directions:
        if name == "scene" and args:
            out["scene"] = args[0]
        elif name == "sleep" and args:
            out["sleep"] = int(args[0])
        elif name in FLAGS:
            out[name] = True
        elif name == "sfx" and args:
            out["sound"] = args[0]
        elif name == "portrait" and args:
            out["portrait"] = tuple(args)
        else:
            out.setdefault("directions", []).append((name, args))
    return out


def scene_lines(node: str, variables: dict | None = None, script: str = INTRO) -> list[dict]:
    return [record(line) for line in ScriptRunner(get(script), node, variables).lines()]


def _said(line: dict) -> str:
    return f"{line['speaker']}: {line['text']}" if line["speaker"] else line["text"]


def legacy() -> dict:
    """The old data/dialogue.json, rebuilt from the script (scenes keep only_before lines)."""
    script = get(INTRO)
    out: dict = {}
    for node in script.nodes:
        if node.endswith("intro"):
            # Without variables both branches of <<if next == ...>> are false: list every line
            # the way the JSON did, each tagged with the condition it was under.
            out[node] = _all_lines(node)
        elif node in ("battle_tip", "end_of_slice"):
            out[node] = _said(scene_lines(node)[0])
        else:
            out[node] = [_said(line) for line in scene_lines(node)]
    return out


def _all_lines(node: str) -> list[dict]:
    script = get(INTRO)
    lines, condition = [], None
    for item in script.node(node).items:
        kind = getattr(item, "kind", None)
        if kind == "if":
            condition = item.arg.split("==")[-1].strip().strip('"')
        elif kind == "endif":
            condition = None
        elif isinstance(item, Line):
            entry = record(item)
            if condition:
                entry["only_before"] = condition
            lines.append(entry)
    return lines
