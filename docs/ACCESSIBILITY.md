# Settings and accessibility

Every setting applies at once, without a restart (Title → Settings, or P → Settings outside a
battle). LEFT/RIGHT change a value; ENTER on a key row waits for the new key.

| Setting | What it does |
|---|---|
| Language | Any language of the menu (docs/LOCALISATION.md). |
| Display | Windowed (a whole-number scale) or fullscreen: the whole display, with the picture at the largest whole-number scale and black bars around it. "Fill" stretches it to the screen with no bars, at a slight cost in sharpness. |
| Volume, Music, Effects, Interface sounds | Four sliders; interface sounds are keys, menus and voices. |
| Text speed | Slow, normal, fast or instant (`text_speeds` in `data/accessibility.json`). |
| Auto-advance | Dialogue moves on by itself (also the A key in a dialogue). |
| Screen shake, Flashes | Reduced motion: off stops the screen from trembling and sprites from flashing when hit. |
| Colour palette | Deuteranopia, protanopia or tritanopia: other colours for the HP bars and the elements, always from the game's 32 colours (`data/accessibility.json`). |
| Grimoire letters | Large: heavier letters on the Grimoire's pages. |
| Anonymous notes, Share my queries | Telemetry, off by default (docs/TELEMETRY.md). |
| Keys | Cast, spell guide, tables, rewind, save Scroll, Codex. |

## Findings

- **A dyslexia-friendly font at pixel size does not exist.** OpenDyslexic, Lexend and Atkinson
  Hyperlegible are outline fonts designed for 12 points and up; at the game's 5x7 pixel letters
  their distinguishing shapes (weighted bottoms, wide apertures) cannot be drawn. The game's own
  letters already avoid the worst confusions (a W that differs from an H, distinct I/l/1, 0/O).
  Instead, text speed (slow) and the dialogue log (L) help the same readers.
- **Large Grimoire letters:** the large option draws heavier letters on the same 4-pixel grid; a
  layout with fewer, bigger characters per line would change every page and is planned with the
  HUD redesign.
