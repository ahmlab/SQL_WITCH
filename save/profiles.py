"""Profiles and slots: one profile per player on the machine, each with three manual slots and
one autosave, in its own folder, so two players never see each other's saves or statistics.

    <root>/profiles/<id>/profile.json     name, look, created, last played
    <root>/profiles/<id>/slot1.json ...   manual slots 1-3 (+ .bak)
    <root>/profiles/<id>/autosave.json    after every guardian defeated, and at the Hearth

Never imports pygame.

STATUS: profiles, three slots + autosave, slot status (empty, ok, damaged),
backups, the most recent save for Continue.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from save.files import Damaged, backup_of, read_json, save_root, write_json
from save.state import GameState

SLOTS = ("1", "2", "3", "auto")


@dataclass
class SlotInfo:
    slot: str
    status: str                     # empty | ok | damaged (has_backup: a good copy exists)
    saved_at: float = 0.0
    at: str = ""
    playtime_s: float = 0.0
    name: str = ""
    has_backup: bool = False


class SaveSystem:
    def __init__(self, root: str | Path | None = None):
        self.root = save_root(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ profiles

    def _dir(self, pid: str) -> Path:
        return self.root / "profiles" / pid

    def profiles(self) -> list[dict]:
        out = []
        for path in sorted((self.root / "profiles").glob("*/profile.json")):
            try:
                data, _ = read_json(path)
            except Damaged:
                continue
            if data:
                out.append(data)
        return sorted(out, key=lambda p: -p.get("last_played", 0))

    def create_profile(self, name: str = "Ada", look: dict | None = None) -> str:
        pid = uuid.uuid4().hex[:10]
        now = time.time()
        write_json(self._dir(pid) / "profile.json",
                   {"id": pid, "name": name, "look": look or {}, "created": now,
                    "last_played": now})
        return pid

    def profile(self, pid: str) -> dict:
        data, _ = read_json(self._dir(pid) / "profile.json")
        if data is None:
            raise KeyError(pid)
        return data

    def delete_profile(self, pid: str) -> None:
        """A profile and every save of it, gone (the Load screen asks first)."""
        import shutil
        folder = self._dir(pid)
        if folder.parent != self.root / "profiles":     # never anything outside profiles/
            raise ValueError(pid)
        shutil.rmtree(folder, ignore_errors=True)

    def has_saves(self, pid: str) -> bool:
        return any(info.status != "empty" for info in self.slots(pid))

    def update_profile(self, pid: str, **fields) -> None:
        data = self.profile(pid)
        data.update(fields)
        write_json(self._dir(pid) / "profile.json", data)

    # ------------------------------------------------------------ slots

    def _slot_path(self, pid: str, slot: str) -> Path:
        if slot not in SLOTS:
            raise ValueError(f"no slot {slot!r}")
        return self._dir(pid) / ("autosave.json" if slot == "auto" else f"slot{slot}.json")

    def save(self, pid: str, slot: str, state: GameState) -> None:
        state.saved_at = time.time()
        write_json(self._slot_path(pid, slot), state.to_dict())
        self.update_profile(pid, last_played=state.saved_at, name=state.player.name,
                            look=state.player.look)

    def load(self, pid: str, slot: str) -> GameState:
        data, status = read_json(self._slot_path(pid, slot))
        if data is None:
            raise KeyError(f"{pid}/{slot} is empty")
        if status == "recovered":            # the file is damaged: the player picks the backup
            raise Damaged(f"{pid}/{slot}")
        return GameState.from_dict(data)

    def load_backup(self, pid: str, slot: str) -> GameState:
        """The last good copy of a damaged slot."""
        path = backup_of(self._slot_path(pid, slot))
        data, _ = read_json(path)
        if data is None:
            raise KeyError(f"{pid}/{slot} has no backup")
        return GameState.from_dict(data)

    def slots(self, pid: str) -> list[SlotInfo]:
        out = []
        for slot in SLOTS:
            path = self._slot_path(pid, slot)
            has_backup = backup_of(path).exists()
            try:
                data, status = read_json(path)
            except Damaged:
                out.append(SlotInfo(slot, "damaged", has_backup=has_backup))
                continue
            if data is None:
                out.append(SlotInfo(slot, "empty", has_backup=has_backup))
                continue
            state = GameState.from_dict(data)
            # A damaged file whose backup is good shows as damaged, with the backup's details:
            # the title offers to load the backup, it never swaps it in silently.
            out.append(SlotInfo(slot, "damaged" if status == "recovered" else status,
                                state.saved_at, state.at, state.playtime_s, state.player.name,
                                has_backup))
        return out

    def latest(self) -> tuple[str, str] | None:
        """(profile, slot) of the most recent good save, for Continue."""
        best = None
        for profile in self.profiles():
            for info in self.slots(profile["id"]):
                if info.status == "ok" and \
                        (best is None or info.saved_at > best[0]):
                    best = (info.saved_at, profile["id"], info.slot)
        return (best[1], best[2]) if best else None
