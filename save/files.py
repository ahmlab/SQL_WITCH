"""Files that survive a crash: atomic writes, one backup per file, damaged-file recovery.

write_json(path, data) writes to a temporary file in the same folder, flushes it to disk and
renames it over the old file (a rename is atomic on every desktop OS), after copying the old
good file to <name>.bak. A crash at any moment leaves either the old file or the new one, never
half of each. read_json(path) returns (data, status): "ok", "missing", or "recovered" when the
file was damaged and its backup was read instead; a damaged file with no good backup raises
Damaged, so the title can show the slot as damaged instead of crashing.

Where files live: save_root() is the per-OS user data folder (platformdirs when installed,
the same conventions otherwise), or the folder given with --save-dir.

Never imports pygame.

STATUS: atomic write, .bak, recovery, per-OS folder.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

APP = "SQLWitch"


class Damaged(Exception):
    """A save file that cannot be read, and no good backup to fall back on."""


def save_root(override: str | Path | None = None) -> Path:
    if override:
        return Path(override)
    try:
        from platformdirs import user_data_dir
        return Path(user_data_dir(APP, appauthor=False))
    except ImportError:
        pass
    home = Path.home()
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / APP
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / APP


def backup_of(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def write_json(path: Path, data, keep_backup: bool = True) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1, ensure_ascii=False)
    if keep_backup and path.exists():
        try:
            json.loads(path.read_text(encoding="utf-8"))      # only a good file is backed up
            shutil.copyfile(path, backup_of(path))
        except (OSError, ValueError):
            pass
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_json(path: Path):
    """(data, status): status is ok, missing or recovered (the backup was used)."""
    path = Path(path)
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), "ok"
    except (OSError, ValueError):
        pass
    backup = backup_of(path)
    if backup.exists():
        try:
            return json.loads(backup.read_text(encoding="utf-8")), "recovered"
        except (OSError, ValueError):
            pass
    raise Damaged(str(path))
