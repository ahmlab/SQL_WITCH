"""Saving: profiles, slots, autosave, the settings file, opt-in telemetry (plan §5.5, prompt 05).

Turns the game's state into files and back, versioned so old saves keep loading.

Must not: Never imports pygame.

Modules: files (atomic writes, backups, the save folder), state (GameState, schema versions,
migrations), profiles (profiles, three slots and the autosave), settings_file (settings.json),
stats (statistics and exports), telemetry (opt-in). How it works for players and editors:
docs/SAVES.md, docs/TELEMETRY.md.

STATUS: profiles, slots, autosave, atomic writes, migrations, settings, statistics, telemetry.
"""
