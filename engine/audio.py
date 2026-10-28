"""Sound effects and music (design doc 7.4), configured in assets/audio/sounds.json.

The game asks for sounds by event name ("hit", "mp_down", ...); sounds.json says which file
plays for each event and how loud. To use your own sound, drop the file into assets/audio/
and change its name in sounds.json: no code changes. A missing file, a missing entry or a
machine without a sound card never stops the game: that sound is simply silent.

STATUS: effects and looping battle music from sounds.json; F2 mutes.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import pygame

AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"
CONFIG = AUDIO_DIR / "sounds.json"


def init_mixer() -> bool:
    """Start the mixer if possible. Call before pygame.init() for a small, snappy buffer."""
    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
        return True
    except pygame.error:
        return False


class Audio:
    def __init__(self, config_path: Path = CONFIG, enabled: bool = True):
        self.config = self._read_config(config_path)
        self.folder = Path(config_path).parent
        self.enabled = enabled and self._mixer_ready()
        self.muted = False
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}
        self._warned: set[str] = set()
        self.played: deque[str] = deque(maxlen=64)     # what was asked for, even when silent
        self.music: str | None = None

    @staticmethod
    def _read_config(path: Path) -> dict:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as error:
            print(f"[audio] cannot read {path}: {error}. Playing without sound.")
            return {}

    @staticmethod
    def _mixer_ready() -> bool:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            return True
        except pygame.error:
            return False                 # no sound card (or a CI machine): stay silent

    def _volume(self, entry: dict) -> float:
        return float(entry.get("volume", 1.0)) * float(self.config.get("master_volume", 1.0))

    def _path(self, entry: dict | None, name: str) -> Path | None:
        if not entry or "file" not in entry:
            return None
        path = self.folder / entry["file"]
        if not path.exists():
            if name not in self._warned:                     # say it once, not every hit
                self._warned.add(name)
                print(f"[audio] '{name}': {path.name} not found in {self.folder}.")
            return None
        return path

    def _load(self, name: str) -> pygame.mixer.Sound | None:
        if name not in self._sounds:
            entry = self.config.get("effects", {}).get(name)
            path = self._path(entry, name)
            sound = None
            if path is not None:
                try:
                    sound = pygame.mixer.Sound(str(path))
                    sound.set_volume(self._volume(entry))
                except pygame.error as error:
                    print(f"[audio] '{name}': cannot play {path.name} ({error}).")
            self._sounds[name] = sound
        return self._sounds[name]

    # ------------------------------------------------------------ what scenes call

    def play(self, name: str) -> None:
        self.played.append(name)
        if not self.enabled or self.muted:
            return
        sound = self._load(name)
        if sound is not None:
            sound.play()

    def play_music(self, name: str) -> None:
        self.music = name
        if not self.enabled:
            return
        entry = self.config.get("music", {}).get(name)
        path = self._path(entry, name)
        if path is None:
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(0.0 if self.muted else self._volume(entry))
            pygame.mixer.music.play(loops=-1, fade_ms=600)
        except pygame.error as error:
            print(f"[audio] music '{name}': {error}")

    def stop_music(self, fade_ms: int = 500) -> None:
        self.music = None
        if self.enabled and pygame.mixer.get_init():
            pygame.mixer.music.fadeout(fade_ms)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.enabled and pygame.mixer.get_init():
            entry = self.config.get("music", {}).get(self.music or "", {})
            pygame.mixer.music.set_volume(0.0 if self.muted else self._volume(entry))
        return self.muted


class Silent(Audio):
    """For tests and tools: remembers what was played, never touches the sound card."""

    def __init__(self, config_path: Path = CONFIG):
        super().__init__(config_path, enabled=False)
