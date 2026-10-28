# SQL Witch: sprite brief

Brief for generating the vertical slice's art (with ChatGPT or by hand).
The game currently draws coloured shapes in their place (`engine/scenes.py`); each
sprite here replaces one of those shapes. Sizes and frames come from §7.2 of the design document.

## 1. Rules that apply to every image

- **Real pixel art.** Logical resolution 320 × 180. Every size below is in game pixels.
- **Only the 32 palette colours** (table below). No gradients, no anti-aliasing, no
  semi-transparent shadows: every pixel is either one palette colour or fully transparent.
- **Transparent background** (PNG with alpha) for everything except the background scene.
- **No black outlines.** Outlines use the dark tone of the same family (e.g. the Slime's
  green body is outlined with `#2e7a4a`, not black).
- **Light from the top left.** Highlight pixel on the upper left, shadow on the lower right.
- **Sprite sheets:** one row per animation, frames left to right, every cell the same size,
  no padding between cells. Example: the Slime at 48 × 40 with a longest animation of 6 frames →
  a 288 × 160 sheet (6 columns × 4 rows).

### Generating with ChatGPT (or any image model)

Image models do not produce real pixel art at exact size: they paint "something that looks like
pixel art" at high resolution, with noise and in-between colours. That is why the steps are:

1. Ask for the image **8 times larger** than the target size (a 48 × 40 sprite → 384 × 320),
   with "each game pixel is an 8 × 8 block of solid colour".
2. Shrink it to the real size with **nearest neighbour** (Aseprite: *Sprite → Sprite Size*,
   "Nearest neighbor" method; or Photoshop with "Nearest Neighbor").
3. Snap every colour to the palette (Aseprite: load the palette and use
   *Sprite → Color Mode → Indexed*).
4. Touch up stray pixels by hand. This is normal and the step that makes the most difference.

I can write a `tools/pixelize.py` script that does steps 2 and 3 automatically
(downscale + snap to the palette). Just ask.

Base prompt (prepend it to each sprite prompt below):

> Pixel art sprite, 16-bit SNES style, flat colours only, no anti-aliasing, no gradients,
> no blur, transparent background. Drawn on an exact grid where each game pixel is an
> 8x8 block of solid colour. Use only this palette: #1a1423 #2b2140 #3e2e5c #5b4388
> #8a63c9 #c6a6f0 #b89a6a #e8d5a8 #f6ecd0 #4a2f25 #7a4b33 #b07020 #f2b33d #ffe08a
> #8c2a3a #d14b4b #2e7a4a #5fbf6a #aae696 #1c706c #3fb6b0 #9ff0e0 #28408c #3c6fd1
> #86b8f0 #544e63 #8a8497 #fbf7ef #d49b7d #f2c8a5 #702c28 #a84834.
> Light comes from the top left. Outlines in the darkest shade of each colour, never pure black.

## 2. The palette (design doc §7.2, figure 11)

Same names as in `engine/render.py`.

| Name | Hex | Name | Hex | Name | Hex | Name | Hex |
|---|---|---|---|---|---|---|---|
| INK | `#1a1423` | NIGHT | `#2b2140` | DUSK | `#3e2e5c` | VIOLET | `#5b4388` |
| LAVENDER | `#8a63c9` | LILAC | `#c6a6f0` | SAND | `#b89a6a` | PARCHMENT | `#e8d5a8` |
| CREAM | `#f6ecd0` | BARK | `#4a2f25` | LEATHER | `#7a4b33` | AMBER | `#b07020` |
| GOLD | `#f2b33d` | BUTTER | `#ffe08a` | WINE | `#8c2a3a` | RED | `#d14b4b` |
| FOREST | `#2e7a4a` | GRASS | `#5fbf6a` | MINT | `#aae696` | TEAL | `#1c706c` |
| AQUA | `#3fb6b0` | FOAM | `#9ff0e0` | NAVY | `#28408c` | BLUE | `#3c6fd1` |
| SKY | `#86b8f0` | SLATE | `#544e63` | GREY | `#8a8497` | WHITE | `#fbf7ef` |
| CLAY | `#d49b7d` | PEACH | `#f2c8a5` | RUST | `#702c28` | BRICK | `#a84834` |

## 3. Assets for the slice, in priority order

Proposed folder: `assets/sprites/`. File names in parentheses.

### 3.1 Asterisk Slime: battler (`slime.png`), cell 48 × 40

The first enemy. A green dome-shaped slime that only knows `SELECT *`. It is the
"World 1-1" of the game: cute, clumsy, a little smug. On its belly it has a golden asterisk
(`*`) that glows: that is its heart and its signature.

| Row | Animation | Frames | Duration |
|---|---|---|---|
| 1 | idle: bobs (squashes 1 px and stretches back) | 4 | 150 ms each |
| 2 | cast: swells, the asterisk shines, spits goo | 6 | 80 ms each |
| 3 | hit: squashed and dented | 2 | 80 ms each |
| 4 | faint: melts into a puddle | 5 | 120 ms each |

The white "hit flash" frame is not drawn: the game generates it from the sprite's silhouette.
An optional extra row is **exhausted**: sagging, half-closed eyes, a drop of sweat (2 frames).

Prompt:

> A cute green slime monster shaped like a dome, front view facing the viewer, two small
> black oval eyes, a glowing golden asterisk symbol (*) on its belly like a heart,
> a small white shine on its upper left. Colours: body #5fbf6a, outline and shadow #2e7a4a,
> highlights #aae696, asterisk #f2b33d with #ffe08a centre. Sprite sheet, 4 rows:
> row 1 idle bounce (4 frames), row 2 casting a spell, swelling and glowing (6 frames),
> row 3 getting hit, squashed (2 frames), row 4 melting into a puddle (5 frames).
> Each frame 48x40 game pixels.

### 3.2 Ada, back view in battle (`ada_back.png`), cell 54 × 60

The protagonist seen from behind (the camera is over her shoulder, Pokémon style). A data
analyst who wakes up as a witch: pointed violet hat with a golden band, long brown hair,
dark robe. She holds an open grimoire (book) in front of her, but from behind it barely shows.

| Row | Animation | Frames | Duration |
|---|---|---|---|
| 1 | idle: breathing, the hat sways slightly | 4 | 150 ms |
| 2 | cast: raises a hand, a glow over the book | 6 | 80 ms |
| 3 | hurt: flinches backwards | 2 | 80 ms |

Prompt:

> A young witch seen from behind, over-the-shoulder view as in Pokemon battles, wearing a
> tall pointed violet hat (#5b4388, brim #3e2e5c) with a golden band (#f2b33d), long brown
> hair (#7a4b33, shadow #4a2f25), dark purple robe (#2b2140). She holds an open spellbook
> in front of her. Sprite sheet, 3 rows: idle breathing (4 frames), casting a spell with
> a raised hand and glowing book (6 frames), hurt recoil (2 frames). Each frame 54x60 game pixels.

### 3.3 Ada, portrait for dialogue (`ada_portrait.png`), cell 32 × 32

Three expressions in a single row: **neutral**, **surprised**, **smug** (pleased with herself).
Face of a woman around 30, glasses, brown hair, witch hat cut off by the top edge.

> Pixel art portrait of a young woman data analyst turned witch, around 30 years old,
> rectangular glasses, brown hair, violet witch hat partly cropped by the frame, three
> expressions side by side: neutral, surprised, smug. Each portrait 32x32 game pixels.

### 3.4 Battle background: Tutorial Glade (`bg_glade.png`), 320 × 100, no transparency

Night clearing. A sky in horizontal bands from `#1a1423` (top) to `#5b4388` (horizon), a few
stars, a crescent moon top right. Pine tree line on the horizon (y ≈ 54). Grass in
`#2e7a4a` / `#5fbf6a`. Two light grass platforms (`#aae696`): one for the Slime around (250, 64)
and one at the bottom left for Ada. **No characters.** The Grimoire covers from y = 100
downwards, so nothing important should sit in the bottom 4 px.

> Pixel art night meadow battle background, 320x100 game pixels, horizontal sky bands from
> very dark purple to violet, few stars, a crescent moon top right, a row of dark green pine
> trees on the horizon, bright green grass below, two lighter oval grass patches where the
> fighters stand (one right-centre, one bottom-left). No characters. Pokemon battle style.

### 3.5 The Grimoire (`grimoire.png`), 320 × 80

The interface book that occupies the bottom 80 px. Brown leather cover (`#4a2f25` / `#7a4b33`)
with corners, two cream pages (`#f6ecd0`) and a spine in the middle. The pages must stay
**empty and flat** (no texture behind the text): the game writes on them. Usable areas
(inside the image): left page x 8–154, right page x 166–312, y 6–70.

Optional: `ink_drip.png` (3 frames of 4 × 8): a drop of grey ink (`#8a8497`) falling.

### 3.6 Title logo (`logo.png`), about 200 × 40

"SQL WITCH" in thick pixel-art letters, `#ffe08a` with an `#b07020` shadow. Optionally, the
asterisk of the Slime or a witch hat over the "I". Must read well over the night sky.

## 4. Later (not needed for the slice)

- Element icons, 8 × 8 each: Fire, Tide, Nature, Storm, Arcane, Earth, Frost, Wind, Light, Shadow.
- Projectiles per element (6 × 6, 3 frames), for the "release" beat of the casting sequence (§7.3).
- The other guardians (Sir Wherewell, the Sorting Sage, …), sizes 40 to 60 px, same animation
  rows as the Slime.
- Ada from the front for the map (about 50 × 68, walking 4 frames in each direction).

## 5. Delivery

Drop the PNGs into `assets/sprites/` with the names above. If you use Aseprite, export the
sheet together with its JSON (`--format json-array --list-tags`, §7.2) and I will slice it from
the JSON. If you only have the PNG, it is fine as long as the cells are the size given here.
