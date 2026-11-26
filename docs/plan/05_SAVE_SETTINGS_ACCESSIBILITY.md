# Prompt 05 — Profiles and saves, settings, fullscreen, player statistics, accessibility, telemetry (opt-in)

Read `docs/plan/00_MASTER_PLAN.md` §4 and the `save/` header. Phase 0 ends when the existing game
runs on top of this.

---

## 0. Read and report

Read `main.py`, `engine/scenes.py` (Game, scene flow, `--start`), `magic/battle.py` (what a battle
needs to resume), `magic/spellbook.py`, `story/codex.py`, and the i18n catalog. Report in 15 lines
what state must persist, what is derived, and where autosave points fall. Stop and wait.

## 1. Save files (`save/`)

- **Profiles** (one per player on the machine: name plus look preview), each with three manual
  slots plus one autosave. The title screen offers New Game, Continue (only when a save exists;
  loads the most recent), Load (choose profile and slot), Settings, Statistics, Credits. JSON,
  versioned with a `schema_version` and a migration table from version 1 onward. Atomic writes (temp file + rename). Corrupt file → the slot shows
  "damaged" and offers the last good backup (keep one `.bak` per slot).
- Contents: protagonist (name, look, gender if D3), level and stats, runes/Codex pages unlocked,
  Scrolls (the view definitions), inventory, story variables from the script engine, region and
  position, companions' state, Fatigue, playtime, settings snapshot, telemetry consent, the
  persistent part of `query_log` (technique signatures per turn for NULL and for learning metrics),
  and named world backups from the Hearth (later).
- Autosave after every guardian defeated (D12) and at the Hearth; manual save from the pause menu
  anywhere outside a battle. Never mid-battle: a battle resumes from its start. Defeat restarts the
  current battle with HP/MP restored, unlimited retries, Fatigue slightly up, retry count logged.
- Save location per OS (`platformdirs` or equivalent); a `--save-dir` flag for tests.

## 2. Settings (`engine/settings.py`, persisted in `settings.json`)

Language; **display**: windowed with integer scale, or fullscreen (true fullscreen covering the whole display, integer scaling with letterbox by default, and a "fill" option with non-integer scaling for players who prefer no bars); master/music/effects/UI volumes; text speed (slow/normal/fast/instant); auto-advance;
screen-shake and flash toggles (reduced motion); colour-blind palette for
the type chart and HP bars (deuteranopia, protanopia, tritanopia); font scale for the Grimoire
(2 sizes, the layout adapts); key bindings for cast, scry, rewind, codex, tables, help; a dyslexia-
friendlier font option if one exists at pixel size (document the finding if not).

## 3. Player statistics (`engine/stats.py`, data from `query_log` and the save)

A Statistics screen (title menu and Grimoire) that shows players how they are doing, per profile,
per run and per battle. It is for the player, not for a teacher. Sections:

- **Casting:** queries cast, free looks, miscasts, overflows, fizzles; rows summoned vs rows read;
  MP spent vs MP wasted; average rows per query; efficiency trend over the last 20 casts.
- **Technique:** which clauses used and how often, first use of each (date and guardian), the
  concept map coloured by use; the same before/after metric as the school report, shown as
  "you started using WHERE in the Filter Keep and have used it 41 times since".
- **Tables:** which tables consulted and how often, which never (with a wink from the Grimoire).
- **The queries themselves:** execution time per query in ms (real, measured), rows scanned vs
  returned, and an optional `EXPLAIN QUERY PLAN` view for experts (shows when an index was used:
  ties into D10).
- **Battles:** time per battle, rounds, retries per guardian, Rewinds, tricks found, Scrolls created.
- **Habits:** play sessions, time at the Hearth vs on the road, Fatigue history (the game's own
  theme, visible to the player).
- Export: a CSV of the player's log and the Scrolls as a `.sql` file (D13).

## 4. Telemetry (opt-in, off by default)

- A consent screen at first launch, with plain-language text (i18n), and a toggle in settings.
- Events, locally queued, sent in batches only with consent: battle start/end, each cast's
  technique signature and outcome (never the query text itself unless the player opts into
  "share my queries"), hint director lines shown, rewinds, tutorial lesson timings, language.
  No names, no free text, no identifiers beyond a random install id.
- The learning metric from the school report (technique use before vs after its guardian) is
  computed locally too, so the game can show the player their own progress in the Codex.
- Backend: a tiny HTTPS endpoint spec in `docs/TELEMETRY.md`; the client works without one.

## 5. Title and system screens

Title as described in §1; settings; statistics; a credits scroll from `CREDITS.md`; a first-launch
flow per profile: language → consent → character creator (prompt 06) → story.

## Tests I expect

- Save round-trip of a full state; migration from v1 fixture; corrupt file recovery; atomic write
  under a simulated crash.
- Every setting applies live without restart; fullscreen toggles and restores; integer scaling
  letterboxes correctly at 1366×768, 1920×1080, 2560×1440 and 3840×2160; reduced motion disables
  shake/flash in a scripted battle; palette switch changes the chart colours.
- Two profiles on one machine never see each other's saves or statistics; defeat restarts the
  battle with the retry count incremented; autosave fires after a guardian and not before.
- Statistics computed from a fixture log match hand-computed values; the export produces a valid
  `.sql` that re-creates the Scrolls in a fresh SQLite database.
- Telemetry sends nothing without consent; with consent, the batch contains no query text unless
  the second toggle is on.
- The existing tutorial → Slime → Knight path runs from a fresh save through the new first-launch
  flow with `--skip-creator` for tests.
