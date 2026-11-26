"""settings.json: the machine's settings, shared by every profile (a snapshot goes in saves).

Every field has a default, so an old or partial file still loads; unknown fields are kept out.
`first_launch` is true until the file exists: the title then asks for a language and for
telemetry consent before anything else.

Never imports pygame (engine/settings.py applies the values to the screen and the sound).

STATUS: settings with defaults, load/save (atomic), first launch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from save.files import Damaged, read_json, write_json

TEXT_SPEEDS = ("slow", "normal", "fast", "instant")
PALETTES = ("normal", "deuteranopia", "protanopia", "tritanopia")
DISPLAYS = ("windowed", "fullscreen")
DEFAULT_BINDINGS = {"cast": "ctrl+return", "help": "f3", "tables": "f4", "rewind": "f6",
                    "scroll": "f7", "codex": "f8", "debug": "f1", "mute": "f2"}


@dataclass
class Settings:
    language: str | None = None            # None: not chosen yet (the first launch asks)
    display: str = "windowed"               # windowed | fullscreen
    scale: int | None = None                # windowed: whole-number scale (None: largest)
    fill: bool = False                      # fullscreen: stretch with no bars (not whole)
    volume: dict = field(default_factory=lambda: {"master": 1.0, "music": 1.0,
                                                  "effects": 1.0, "ui": 1.0})
    text_speed: str = "normal"
    auto_advance: bool = False
    screen_shake: bool = True               # reduced motion: off
    flashes: bool = True                    # reduced motion: off
    palette: str = "normal"                 # colour-blind palettes for HP bars and elements
    grimoire_font: str = "normal"           # normal | large
    bindings: dict = field(default_factory=lambda: dict(DEFAULT_BINDINGS))
    telemetry: bool = False                 # opt-in, off by default
    share_queries: bool = False             # a second opt-in: send the query text too
    consent_asked: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = cls.__dataclass_fields__
        settings = cls(**{k: v for k, v in (data or {}).items() if k in known})
        settings.bindings = dict(DEFAULT_BINDINGS, **(settings.bindings or {}))
        settings.volume = dict(cls().volume, **(settings.volume or {}))
        return settings


class SettingsFile:
    def __init__(self, root: Path):
        self.path = Path(root) / "settings.json"

    @property
    def first_launch(self) -> bool:
        return not self.path.exists()

    def load(self) -> Settings:
        try:
            data, _ = read_json(self.path)
        except Damaged:
            data = None                          # a broken settings file: start from defaults
        return Settings.from_dict(data or {})

    def save(self, settings: Settings) -> None:
        write_json(self.path, settings.to_dict())
