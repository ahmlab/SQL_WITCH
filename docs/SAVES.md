# Saves, profiles and settings

## Where things are

Everything lives in one folder per computer: `~/.local/share/SQLWitch` on Linux,
`~/Library/Application Support/SQLWitch` on macOS, `%APPDATA%\SQLWitch` on Windows (or the folder
given with `python main.py --save-dir FOLDER`).

| File | What it holds |
|---|---|
| `settings.json` | The settings of this computer, shared by every profile. |
| `profiles/<id>/profile.json` | A player: name, look, when they last played. |
| `profiles/<id>/slot1.json` … `slot3.json` | Manual saves (from the pause menu, P). |
| `profiles/<id>/autosave.json` | Written after every guardian defeated (and at the Hearth, later). |
| `*.bak` | The previous good copy of each file. |
| `telemetry/queue.jsonl`, `install.json` | Only if the player agreed to telemetry (docs/TELEMETRY.md). |
| `exports/<profile>/` | The statistics export: `log.csv` and `scrolls.sql`. |

Each profile has its own folder: two players on one computer never see each other's saves or
statistics.

## What a save holds

The protagonist (name, look, gender), where the story stands, the guardians beaten and the
retries against each, runes and Codex pages, Scrolls, story variables, Fatigue, playtime, a copy
of the settings, the telemetry choice, and the player's own log: one line per cast (technique
signature, rows, MP, real execution time, query plan). The statistics screen reads it.

A battle is never saved halfway: Continue starts the battle again from its beginning. Losing
restarts the battle with HP and MP restored; the retry is counted and Fatigue rises a little
(`rise.defeat` in `data/fatigue.json`).

## Safety

Every file is written to a temporary file first and then renamed over the old one, so a crash
or a power cut leaves the old save or the new one, never half of each. If a save is damaged
anyway, the Load screen shows it as damaged and offers its last good copy (ENTER).

Saves carry a `schema_version`. When the format changes, `save/state.py` gets a migration from
the old version to the new one (`MIGRATIONS`), and old saves keep loading. A version-1 save (the
school build) is tested in `tests/fixtures/save_v1.json`.
