# Prompt 01 — Foundations: repository reset, CLAUDE.md v2, licence, CI

Paste as the first message of a new session at the repo root. Read `00_MASTER_PLAN.md` first;
it is in `docs/plan/` (put it there before starting).

---

## 0. Read and report (write no code)

Read `docs/plan/00_MASTER_PLAN.md`, the current `CLAUDE.md`, `README.md`, `docs/`, the module
headers of every package, `data/*.json`, `tests/`, and run `pytest -q`. Then report in at most 20
lines: what exists, what the plan changes, which existing modules the plan contradicts, and the
three riskiest spots. Stop and wait.

## 1. Rewrite `CLAUDE.md` for the full game

Keep it under 200 lines. It must contain: the thesis and pillars (short), the Decision Log with the
current state of D0–D8 (copy from the plan, mark undecided ones), the package map from plan §4, the
six hard rules, the process rules from plan §8, and the content rule: every player-visible string is
an i18n key, every tunable number lives in a data file.

Add a **"Do not"** list: never import pygame outside `engine/`; never consume the battle `rng` for
anything visual; never bypass the Grimoire; never commit; never add a UNIQUE or index on
`spells.name`; never produce user-visible text in code.

## 2. Licence and credits

Replace the CC0 `LICENSE` with the split decided in D6 (if not decided, create `LICENSE-CODE` as
MIT and `LICENSE-ASSETS` as "all rights reserved, pending decision", and say so in the README).
Add `CREDITS.md` with the three authors, the AI-assisted-production statement from D8, and a
section for third-party fonts and tools with their licences.

## 3. Repository layout

Create the new packages as empty modules with headers in the existing style (purpose,
responsibilities, must-not, status): `story/`, `i18n/`, `save/`, `magic/world.py`,
`magic/spellbook.py`, `magic/fatigue.py`, `engine/animation.py`, `engine/dialogue.py`,
`engine/hud.py`, `engine/settings.py`. Move the design PDF and the plan folder under `docs/plan/`.
Do not delete anything that works.

## 4. CI and packaging skeleton

- GitHub Actions: `pytest -q` on Linux, macOS and Windows on every push (SDL dummy drivers).
- A `tools/package.py` that builds a runnable bundle with PyInstaller for the current OS, and a CI
  job that runs it weekly and uploads the artefact. The bundle must start, show the title, and quit
  from a `--smoke-test` flag.
- `requirements.txt` pinned; `environment.yml` unchanged.

## 5. The Chinese-typing spike (do this before anything else in Phase 0)

A throwaway script `tools/spike_ime.py` that opens a window, enables text input, and shows what
`TEXTINPUT` and `TEXTEDITING` events deliver when the user types with a Chinese IME, plus a CJK
pixel font rendering the result (candidate fonts: Fusion Pixel, Zpix, GNU Unifont as the fallback;
check their licences). Document the findings in `docs/spikes/ime.md`. If composition events do not
arrive or the font path is unworkable, say so loudly: it reopens Decision D0.

## Tests I expect

- All existing tests still pass; new empty modules import cleanly.
- CI runs green on three OSes; the packaged bundle passes `--smoke-test` on at least Linux.
- A test asserting no file under `engine/`, `story/`, `magic/`, `ai/` contains a literal
  user-facing string outside the i18n catalog (start with a lint that flags string literals passed
  to the text renderer; it will fail until prompt 04 lands, mark it `xfail` until then).
