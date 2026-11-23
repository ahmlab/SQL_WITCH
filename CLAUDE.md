# CLAUDE.md — SQL Witch, the full game

Read this first in every session. The roadmap is `docs/plan/00_MASTER_PLAN.md`; the build prompts
are `docs/plan/01_…` onwards. When a prompt and the plan disagree, the plan wins; when the plan
and the team disagree, update the plan first.

## Thesis

SQL Witch teaches SQL to people who fear that learning is pointless because a machine writes
queries better. The game's answer, through play: you will not type most queries in your life,
and you still need to understand them, because understanding lets you direct the machine.

## Pillars (every feature must pass them)

1. Queries are the controller: every effect comes from a real query on a real database.
2. Understanding beats typing: reward reading, choosing, limiting, filtering, planning; never speed.
3. Freedom with consequences, and a way back: any SQL is allowed; the world reacts; Rewind exists.
4. Enemies teach; the Codex remembers: techniques are demonstrated and recorded, never locked.
5. The quest is a party, and the party rests (Hearth, companions, letters).
6. Fun on every keystroke: typing is casting (sound, light, ink).
7. Every player, every language: all text is localised; SQL keywords stay in English.

## Decision Log (state on 23 Nov 2026)

| # | Decision | State |
|---|---|---|
| D0 | Engine | pygame-ce for Phase 0–1; re-decide at the end of Phase 1. |
| D1 | Stores | itch.io first, Steam second. No web, no mobile. |
| D2 | Protagonist | Decided: custom name and look, fixed situation; Ada is the default. |
| D3 | Gender | Decided: feminine or masculine in the creator; ICU `select` on `player.gender`. |
| D4 | Languages | Decided: EN, ES, ZH-Hans, ZH-Hant first; then EU-24 + ID with native reviewers. |
| D5 | SQL dialect | SQLite, with Codex notes on PostgreSQL/MySQL. |
| D6 | Licence | Open. The author asked not to change it now (LICENSE is still CC0). |
| D7 | Business model | Open; decide before Phase 2. |
| D8 | AI in production | Decided: code and text AI-drafted, human-approved; visual design generative AI, credited. |
| D9 | Text resolution | Decided: text and UI at 2x (640×360) over the 320×180 world. |
| D10 | Expert freedom | Decided: triggers, indexes, views, transactions allowed and rewarded (Trickster). |
| D11 | Platforms | Decided: desktop only (Windows, macOS, Linux). |
| D12 | Defeat | Decided: losing restarts the level, unlimited retries, nothing lost. |
| D13 | Learning | Decided: by interaction only, no drills; concepts recur (`data/concepts.json`). |
| — | Spell names | Decided: stay English in the database (they are data); only narration translates. |

## Package map

```
engine/   pygame, thin: scenes, render, animation, grimoire, dialogue UI, textinput, hud,
          audio, settings, the i18n glue (fonts on screen)
story/    dialogue scripts, the Hint Director, the Codex            (no pygame)
magic/    db, guard (sandbox), cast, rules, battle, world (integrity, snapshots, reactions),
          fatigue/focus, spellbook (Scrolls = views), tutorial      (no pygame)
ai/       brains (FSM, goals, ...), styles, roster, perception, steering   (no pygame)
i18n/     catalog, ICU messages (plural, select), locales, pseudo-locale   (no pygame)
save/     slots, autosave, settings file, opt-in telemetry              (no pygame)
sim/      headless battles, balance, learning metrics
tools/    generators (sounds, music, pixelize), packaging, translation, spikes
data/     every piece of content: CSV tables, scripts, hints, reactions, codex, catalogs
docs/     how a non-programmer changes each system; docs/plan has the roadmap
```

## The six hard rules

1. `magic/`, `ai/`, `story/`, `i18n/`, `save/` never import pygame.
2. One pipeline for player and foe queries (`guard.inspect` → `guard.run_query` → `cast.resolve`).
3. A brain's Intent is discarded after Express; only executed queries have effects.
4. One `random.Random` per battle, passed explicitly; visual randomness uses `game.vfx`.
5. All text the player sees comes from the i18n catalog, by key (`i18n.t`). No literal UI strings.
6. All content (spells, foes, dialogue, hints, reactions, music cues) is data, not code.

Content rule: every player-visible string is an i18n key, every tunable number lives in a data
file (`data/*.json`, `data/*.csv`, `assets/audio/sounds.json`).

## Do not

- Never import pygame outside `engine/` (and `tools/`, `main.py`, tests).
- Never consume the battle `rng` for anything visual or audible.
- Never bypass the Grimoire: no menu, key or cheat that changes the world without a query.
- Never add a UNIQUE constraint or an index on `spells.name` (name uniqueness is checked in code,
  across all tables, so the error can be in character).
- Never produce user-visible text in code; add a key to `data/i18n/en.json` instead.
- Never weaken program safety: `ATTACH`, `load_extension`, file-system PRAGMAs, `VACUUM`, more
  than one statement per cast (except one transaction block) and the time budget stay refused.

(The plan says "never commit". The author overrode it: commit and push each finished step to the
working branch, `claude/happy-goldberg-og671f`.)

## Process (what worked)

1. One workstream per session, in the order of `docs/plan/`.
2. Every prompt begins with read-and-report and ends with the tests it expects.
3. Anything with a voice (story, dialogue, hints, reactions) is a data file first, edited by a
   human before it is wired in.
4. Every feature ships with its data file, its tests, and a paragraph in `docs/` explaining how a
   non-programmer changes it.
5. Playtest at every phase exit.

## Working here

- `python -m pytest -q` runs the suite (headless: SDL dummy drivers in `tests/conftest.py`);
  `--runslow` adds the full music re-render.
- `python main.py --start tutorial|slime|knight`, `--seed N`, `--smoke-test` (CI and packaging).
- Module headers follow one style: purpose, how it works, what it must not do, `STATUS:` line.
- Comments explain why, in plain English.
