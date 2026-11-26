# Art pipeline: layered characters

The protagonist is built from layers the player chooses in the character creator: body, outfit,
hair, hat and accessory (`data/characters/witch.json` lists the options). Each option is one
sprite sheet; the game stacks them, recolours them and animates them.

## Folders

```
assets/characters/witch/<layer>/<option>.png + .json            the sprite, seen from behind
assets/characters/witch/portrait/<layer>/<option>.png + .json   the dialogue portrait
```

Export from Aseprite with `--format json-array --list-tags`: frames one after another, each with
its duration, and one tag per animation. Every option of every layer must have **every tag**
with the **same number of frames** and the **same frame size** (20 x 41 for the sprite,
32 x 32 for the portrait):

| Tag | Frames | Notes |
|---|---|---|
| `idle` | 4 | loops |
| `cast` | 6 | frame 4 fires the projectile (an event in `witch.json`) |
| `hit` | 3 | interrupts anything but `faint` |
| `faint` | 5 | terminal: holds its last frame |
| `victory`, `rest` | 4, 2 | loop |
| `walk_left`, `walk_right`, `walk_up`, `walk_down` | 4 each | loop |

A portrait sheet has one frame per emotion, each a tag: `neutral`, `happy`, `sad`, `angry`,
`surprised`.

## Colours

Paint only with the game's 32 palette colours (`engine/render.py`) and these **swap colours**,
which the game replaces with the player's choices when it loads the sheet (light and dark):

| Part | Light | Dark |
|---|---|---|
| skin | 255, 0, 255 | 190, 0, 190 |
| hair | 0, 255, 255 | 0, 180, 180 |
| outfit (primary) | 255, 255, 0 | 180, 180, 0 |
| trim (secondary) | 0, 255, 0 | 0, 170, 0 |

The creator offers named pairs of palette colours for each part (`colours` in `witch.json`), so
any combination stays inside the palette. The game also draws a one-pixel ink outline and a
small shadow; do not paint them.

## Checking and importing

```bash
python -m tools.import_sprites validate
```

It checks every sheet and every portrait: all tags, frame counts, frame sizes, and that every
pixel is a palette or swap colour. To bring in an artist's export (a folder laid out like
`assets/characters/witch/`), check and copy it in one step:

```bash
python -m tools.import_sprites import path/to/export
```

Until the art arrives, `python -m tools.import_sprites placeholders` draws simple programmatic
layers for every option, so the creator, the battle and the portraits all work. The default look
(Ada) keeps the artist's hand-made battle sprite (`assets/sprites/ada_back.png`).
