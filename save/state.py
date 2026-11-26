"""The state a save holds, and how old saves become new ones (schema_version, migrations).

GameState is everything that persists between sessions: the protagonist (name, look, gender,
decision D3), progress (where the story stands, guardians beaten, retries per guardian),
runes and Codex pages, Scrolls (the view definitions), inventory, story variables of the script
engine, region and position, companions, Fatigue, playtime, a snapshot of the settings, the
telemetry consent, the persistent part of query_log (one record per cast: technique signature,
rows, MP, time; statistics and learning metrics read it) and named world backups (the Hearth,
later). Derived things (the battle database, a guardian's brain) are rebuilt, never saved.

A battle is never saved halfway: a battle resumes from its start.

Migrations: MIGRATIONS[n] turns a version-n dict into version n+1; load() applies them in
order, so a save from version 1 still opens after many updates.

Never imports pygame.

STATUS: GameState, to_dict/from_dict, schema v2, migration from v1.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = 2


@dataclass
class Player:
    name: str = "Ada"
    gender: str = "feminine"              # feminine | masculine (D3)
    look: dict = field(default_factory=dict)   # hair, colours, hat... (prompt 06)


@dataclass
class GameState:
    player: Player = field(default_factory=Player)
    at: str = "tutorial"                   # where the story stands: tutorial, a guardian, end
    beaten: list[str] = field(default_factory=list)
    retries: dict[str, int] = field(default_factory=dict)
    runes: list[str] = field(default_factory=list)
    codex: list[dict] = field(default_factory=list)
    scrolls: dict[str, str] = field(default_factory=dict)
    inventory: dict[str, int] | None = None    # None: the data defaults (the Hearth, prompt 08)
    story: dict = field(default_factory=dict)  # <<set>> variables of the scripts
    region: str = "glade"
    position: list[int] = field(default_factory=lambda: [0, 0])
    companions: dict = field(default_factory=dict)
    fatigue: float = 0.0
    focus: dict = field(default_factory=dict)          # the Focus streak and charges
    playtime_s: float = 0.0
    settings: dict = field(default_factory=dict)
    telemetry: dict = field(default_factory=lambda: {"consent": False, "share_queries": False})
    log: list[dict] = field(default_factory=list)       # one record per cast (save/stats.py)
    battles: list[dict] = field(default_factory=list)   # one record per battle
    sessions: list[dict] = field(default_factory=list)  # play sessions: start, seconds
    time_in: dict = field(default_factory=dict)         # seconds per place: story, battle...
    backups: dict[str, str] = field(default_factory=dict)   # named world backups (later)
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    saved_at: float = 0.0

    def to_dict(self) -> dict:
        data = asdict(self)
        data["schema_version"] = SCHEMA_VERSION
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        data = migrate(dict(data))
        data.pop("schema_version", None)
        player = Player(**data.pop("player", {}))
        known = {f for f in cls.__dataclass_fields__}
        return cls(player=player, **{k: v for k, v in data.items() if k in known})


def _v1_to_v2(data: dict) -> dict:
    """Version 1 (the school build's save): a name, runes, the next guardian, scrolls."""
    return {
        "schema_version": 2,
        "player": {"name": data.get("name", "Ada"), "gender": "feminine", "look": {}},
        "at": data.get("progress", "tutorial"),
        "beaten": list(data.get("beaten", [])),
        "runes": list(data.get("runes", [])),
        "codex": [],
        "scrolls": dict(data.get("scrolls", {})),
        "playtime_s": float(data.get("playtime", 0)),
        "saved_at": float(data.get("saved_at", time.time())),
    }


MIGRATIONS = {1: _v1_to_v2}


def migrate(data: dict) -> dict:
    version = int(data.get("schema_version", 1))
    while version < SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version = int(data.get("schema_version", version + 1))
    return data
