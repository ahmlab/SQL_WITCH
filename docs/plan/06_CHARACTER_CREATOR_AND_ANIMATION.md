# Prompt 06 — Character creator and sprite animation

Read `docs/plan/00_MASTER_PLAN.md` D2–D3 and §5.3. The protagonist is a frozen image today; the
player will now design them, and they will move.

---

## 0. Read and report

Read `engine/render.py` (sprite loading, the artist's witch), `engine/scenes.py` (where the
protagonist is drawn in battle, dialogue and the tutorial), `assets/` and the artist's source
files if present, `data/witch.csv`, and the name uniqueness rules in `magic/db.py`. Report in 15
lines how sprites are loaded and drawn, and your plan for layered palette-swap sprites. Stop.

## 1. Layered sprite system (`engine/animation.py`)

- A character is a stack of layers: body, hair, outfit, hat, accessory, each a sprite sheet with
  the same animation tags and frame counts. Colours are **palette-swapped** at load time from a
  small set of indexed "swap" colours in the source art to the chosen colours (`PixelArray` or a
  precomputed lookup; no per-frame cost).
- Animation controller: tags from Aseprite JSON (`--format json-array --list-tags`): `idle`,
  `cast`, `hit`, `faint`, `victory`, `walk_<dir>`, `rest`; frame durations from the file; events on
  frames (`cast` frame 4 fires the projectile) so animation and battle events stay in sync; a
  state machine with transitions (idle ↔ cast → idle; hit interrupts; faint is terminal).
- Guardians use the same controller (the Slime already has idle; add cast/hit/faint tags).
- Integer-pixel positioning, flip for facing, a cheap drop shadow, and an outline pass that
  preserves the 32-colour palette.

## 2. Character creator (`engine/creator.py`, first-launch flow)

- Name: 1–12 characters, any script (Chinese names via IME), trimmed, no quotes/backslashes/
  semicolons (they would break a literal), must not equal any name in the data files or any SQL
  keyword (case-insensitive), with an in-character refusal and a suggestion. Default: Ada.
- Look: hair style (3+), hair colour, skin tone, outfit colour primary/secondary, hat style, one
  accessory (glasses, scarf, book charm). All from the project palette so nothing clashes.
- Gender: feminine or masculine (D3). It drives the ICU `select` in every inflecting language and
  nothing else mechanically.
- **Portraits are layered too:** the dialogue portrait (and its emotions) is built from the same
  layer choices and colours as the sprite, so the creator changes both. The validator checks that
  every portrait emotion exists for every layer option.
- Live preview with the idle animation and the portrait; randomise button; the result is stored in the save and in
  the `witch` row's `name`; the battle database uses the player's name everywhere Ada was used.
- Opening the creator later from the Hearth (a mirror) lets the player change look, not name
  (the name is in Scrolls and the log; renaming needs a Codex note about identifiers — later).

## 3. Art pipeline (`docs/ART_PIPELINE.md` + `tools/import_sprites.py`)

- Folder convention per character and layer; a validator that checks every layer has every tag
  with identical frame counts and sizes, and that only swap colours and palette colours are used.
- A placeholder generator that draws programmatic layers for every option so the system is
  playable before the artist delivers.

## Tests I expect

- Palette swap maps every swap colour and nothing else; the output uses only palette colours.
- Controller: transitions, interrupt on hit, frame events fire exactly once, deterministic given
  elapsed time.
- Name rules: Chinese name accepted; `Ember`, `SELECT`, `o'malley` refused with the right keys;
  the saved name appears in `witch` and in a cast report.
- Creator round-trips through the save; the mirror changes look only.
- Validator rejects a sheet with a missing tag or an off-palette pixel.
