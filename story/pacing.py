"""The typewriter: when each character of a line appears, and how it sounds.

A line is revealed by time, not by frames (so a slow machine paces it the same way):
- every character takes 1000 / cps ms, cps from data/pacing.json, slower for CJK characters
  (one Chinese character carries a word), times the speaker's own speed and any {speed} command;
- punctuation adds a pause after it (a comma a little, a full stop more), per language;
- {pause N} waits N ms; {instant} shows the rest of the line at once.
Typewriter.visible(ms) says how many characters are shown at a moment; the scene draws that many.

Voices: each speaker has a blip (a timbre and a note) played every few letters, the same idea
as the typing notes. voice() says which.

Never imports pygame.

STATUS: schedule by time, CJK speed, per-language punctuation, pauses, instant, voices,
the player's text speed.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from functools import lru_cache

from magic.db import DATA_DIR
from story.script import Token, tokens


@lru_cache(maxsize=1)
def settings() -> dict:
    with open(DATA_DIR / "pacing.json", encoding="utf-8") as f:
        return json.load(f)


def is_cjk(char: str) -> bool:
    code = ord(char)
    return (0x3000 <= code <= 0x30FF or 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF
            or 0xF900 <= code <= 0xFAFF or 0xFF00 <= code <= 0xFFEF)


# The player's text speed (settings): a multiple of every speed; 0 shows lines at once.
SPEED = {"factor": 1.0}


def set_text_speed(factor: float) -> None:
    SPEED["factor"] = factor


class Typewriter:
    def __init__(self, markup: str | list[Token], speaker: str = "", locale: str = "en"):
        data = settings()
        self.tokens = tokens(markup) if isinstance(markup, str) else markup
        base = data["speakers"].get(speaker, 1.0)
        punctuation = dict(data["punctuation"]["default"])
        punctuation.update(data["punctuation"].get(locale, {}))
        self.times: list[float] = []              # when character i appears, in ms
        self.text = ""
        t, speed, instant = 0.0, 1.0, SPEED["factor"] <= 0
        for token in self.tokens:
            if token.kind == "pause":
                t += token.value
            elif token.kind == "speed":
                speed = token.value or 1.0
            elif token.kind == "instant":
                instant = True
            else:
                for char in token.text:
                    cps = data["cps"]["cjk" if is_cjk(char) else "latin"] * base * speed * \
                        max(SPEED["factor"], 0.01)
                    if not instant:
                        t += 1000.0 / cps
                    self.times.append(t)
                    self.text += char
                    if not instant:
                        t += punctuation.get(char, 0)
        self.total_ms = t

    def __len__(self) -> int:
        return len(self.text)

    def visible(self, elapsed_ms: float) -> int:
        """How many characters are shown `elapsed_ms` after the line started."""
        return bisect_right(self.times, elapsed_ms)

    def done(self, elapsed_ms: float) -> bool:
        return self.visible(elapsed_ms) >= len(self.text)


def voice(speaker: str) -> tuple[str, int]:
    """(sound event, variant) of a speaker's blip: e.g. ("voice_square", 4)."""
    data = settings()["voices"]
    v = data.get(speaker, data.get("", {"timbre": "triangle", "note": 3}))
    return f"voice_{v['timbre']}", int(v["note"]) - 1


def style_of(speaker: str) -> dict:
    data = settings()
    kind = data["speaker_style"].get(speaker, "companion" if speaker else "narrator")
    return dict(data["styles"][kind], kind=kind)
