# Credits

## Author

**Alejandro H.** — design, direction, writing, review.

## How this game is made (decision D8)

SQL Witch is itself an argument about working with machines, so we say plainly how it is made:

- **Code and text** are drafted with an AI assistant (Claude, by Anthropic) and reviewed,
  edited and approved by the author. Nothing ships without a human reading it.
- **Visual design** (backgrounds, portraits, props) is made with generative AI, then reduced to
  the game's 32-colour palette and touched up (`tools/pixelize.py`, `docs/SPRITES.md`).
- **Sound effects and music** are synthesised by code written for this game
  (`tools/make_sounds.py`, `tools/make_music.py`), from the Python standard library only.

## Third-party software

| What | Licence | Used for |
|---|---|---|
| [pygame-ce](https://pyga.me/) | LGPL-2.1 | window, input, drawing, sound |
| [SDL 2](https://libsdl.org/) | zlib | under pygame-ce |
| [sqlglot](https://github.com/tobymao/sqlglot) | MIT | parsing the player's SQL |
| [SQLite](https://sqlite.org/) | public domain | the world's database |
| [Babel](https://babel.pocoo.org/) | BSD-3-Clause | CLDR plural rules and locale formatting |
| [pytest](https://pytest.org/) | MIT | tests |
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0 with a bootloader exception (bundles may be distributed under any licence) | packaging |

## Fonts

| Font | Licence | Used for |
|---|---|---|
| The game's own 3x5 and 5x7 pixel fonts (`engine/render.py`) | the game's licence | Latin text |
| [GNU Unifont](https://unifoundry.com/unifont/) (`assets/fonts/unifont.otf`) | SIL OFL 1.1, or GPL-2.0-or-later with the GNU font embedding exception (dual-licensed upstream) | Chinese, Greek, Cyrillic and every character the pixel fonts lack |

Candidates evaluated for Chinese and not bundled (see `docs/spikes/ime.md`): Fusion Pixel Font and
Zpix (both under the SIL OFL 1.1), unreachable from the build environment; they can replace
Unifont later without code changes.
