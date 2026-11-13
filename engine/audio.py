"""Sound effects and music (design doc 7.4), configured in assets/audio/sounds.json.

The game asks for sounds by event name ("hit", "mp_down", ...); sounds.json says which file
plays for each event and how loud. To use your own sound, drop the file into assets/audio/
and change its name in sounds.json: no code changes. A missing file, a missing entry or a
machine without a sound card never stops the game: that sound is simply silent.

Music plays on two reserved mixer channels: the battle theme, and the danger theme that
replaces it while Ada's HP is low. Switching fades one out and the other in; the battle theme
is paused rather than stopped, so it resumes where it was. A music entry may list several
files: the scene picks one per battle (pick_track), never with the battle's random generator.

STATUS: effects, battle themes chosen from sounds.json, the danger cross-fade; F2 mutes.
"""

from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path

import pygame

AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"
CONFIG = AUDIO_DIR / "sounds.json"
MUSIC_FADE_MS = 600          # every music change fades: no hard cuts, no clicks
THEME, DANGER = 0, 1         # the two reserved channels


def pick_track(files: list[str], last: str | None, rng) -> int:
    """Which of a music entry's files to play: any of them, but not the one just played
    (a retry after a defeat should not sound the same). `rng` must be a visual-only random
    generator, never the battle's: the same seed must replay the same fight."""
    if len(files) <= 1:
        return 0
    options = [i for i, name in enumerate(files) if name != last] or list(range(len(files)))
    return rng.choice(options)


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
        self.counts: Counter[str] = Counter()           # how often, since the start
        self.music: str | None = None                   # the music entry asked for ("slime")
        self.music_file: str | None = None              # the file picked for it
        self.danger = False                             # the danger theme is on
        self.music_log: list[str] = []                  # every music request, even when silent
        # Each channel's fade: [volume now, volume wanted, what to do once silent].
        self._fades = {THEME: [0.0, 0.0, None], DANGER: [0.0, 0.0, None]}
        self._channels: tuple | None = None

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

    def _load(self, name: str, variant: int = 0) -> pygame.mixer.Sound | None:
        entry = self.config.get("effects", {}).get(name)
        files = entry.get("files") if entry else None
        if files:                                   # several files: pick one by variant
            entry = dict(entry, file=files[variant % len(files)])
            key = f"{name}#{variant % len(files)}"
        else:
            key = name
        if key not in self._sounds:
            path = self._path(entry, name)
            sound = None
            if path is not None:
                try:
                    sound = pygame.mixer.Sound(str(path))
                    sound.set_volume(self._volume(entry))
                except pygame.error as error:
                    print(f"[audio] '{name}': cannot play {path.name} ({error}).")
            self._sounds[key] = sound
        return self._sounds[key]

    # ------------------------------------------------------------ what scenes call

    def play(self, name: str, variant: int = 0) -> None:
        """Play an effect. An event with a "files" list (like typing) uses file `variant`."""
        self.played.append(name)
        self.counts[name] += 1
        if not self.enabled or self.muted:
            return
        sound = self._load(name, variant)
        if sound is not None:
            sound.play()

    # ------------------------------------------------------------ music

    def music_files(self, name: str) -> list[str]:
        """The files a music entry may play ("file" or a "files" list)."""
        entry = self.config.get("music", {}).get(name) or {}
        return list(entry.get("files") or ([entry["file"]] if "file" in entry else []))

    def _music_sound(self, name: str, filename: str) -> pygame.mixer.Sound | None:
        key = f"music:{filename}"
        if key not in self._sounds:
            entry = dict(self.config.get("music", {}).get(name) or {}, file=filename)
            path, sound = self._path(entry, name), None
            if path is not None:
                try:
                    sound = pygame.mixer.Sound(str(path))
                    sound.set_volume(self._volume(entry))
                except pygame.error as error:
                    print(f"[audio] music '{name}': cannot play {path.name} ({error}).")
            self._sounds[key] = sound
        return self._sounds[key]

    def _channel(self, which: int):
        if self._channels is None:
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(2)              # effects never take the music's channels
            self._channels = (pygame.mixer.Channel(THEME), pygame.mixer.Channel(DANGER))
        return self._channels[which]

    def _fade(self, which: int, wanted: float, then: str | None = None) -> None:
        self._fades[which][1:] = [wanted, then]

    def play_music(self, name: str, choice: int = 0) -> str | None:
        """Start a music entry from its first bar (file `choice` of its list). Returns the file."""
        files = self.music_files(name)
        filename = files[choice % len(files)] if files else None
        self.music, self.music_file, self.danger = name, filename, False
        self.music_log.append(f"play {name} {filename}")
        if not self.enabled or filename is None:
            return filename
        sound = self._music_sound(name, filename)
        self._channel(DANGER).stop()
        self._fades[DANGER] = [0.0, 0.0, None]
        if sound is not None:
            self._fades[THEME] = [0.0, 1.0, None]
            self._channel(THEME).set_volume(0.0)
            self._channel(THEME).play(sound, loops=-1)
        return filename

    def set_danger(self, on: bool) -> None:
        """Cross-fade to the danger theme (on) or back to the battle theme (off), which picks
        up where it was paused. Asking twice for the same thing does nothing: staying low
        never restarts the danger theme."""
        if on == self.danger or self.music is None:
            return
        self.danger = on
        self.music_log.append("danger on" if on else "danger off")
        if not self.enabled:
            return
        danger_files = self.music_files("danger")
        if not danger_files:
            return
        theme, danger = self._channel(THEME), self._channel(DANGER)
        if on:
            self._fade(THEME, 0.0, "pause")
            if not danger.get_busy():
                sound = self._music_sound("danger", danger_files[0])
                if sound is not None:
                    self._fades[DANGER][0] = 0.0
                    danger.set_volume(0.0)
                    danger.play(sound, loops=-1)
            self._fade(DANGER, 1.0)
        else:
            self._fade(DANGER, 0.0, "stop")
            theme.unpause()
            self._fade(THEME, 1.0)

    def update(self, dt: int) -> None:
        """Move the music fades on by dt milliseconds (Game.update calls this every frame)."""
        if not self.enabled or self._channels is None:
            return
        step = dt / MUSIC_FADE_MS
        for which, fade in self._fades.items():
            now, wanted, then = fade
            if now == wanted:
                continue
            now = min(wanted, now + step) if wanted > now else max(wanted, now - step)
            fade[0] = now
            channel = self._channel(which)
            channel.set_volume(0.0 if self.muted else now)
            if now == 0.0 and then == "pause":
                channel.pause()
            elif now == 0.0 and then == "stop":
                channel.stop()

    def stop_music(self, fade_ms: int = 500) -> None:
        self.music, self.music_file, self.danger = None, None, False
        self.music_log.append("stop")
        if self.enabled and pygame.mixer.get_init() and self._channels is not None:
            for which in (THEME, DANGER):
                channel = self._channel(which)
                channel.unpause()
                channel.fadeout(fade_ms)
                self._fades[which] = [0.0, 0.0, None]

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.enabled and pygame.mixer.get_init() and self._channels is not None:
            for which, fade in self._fades.items():
                self._channel(which).set_volume(0.0 if self.muted else fade[0])
        return self.muted


class Silent(Audio):
    """For tests and tools: remembers what was played, never touches the sound card."""

    def __init__(self, config_path: Path = CONFIG):
        super().__init__(config_path, enabled=False)
