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
| [OpenCC](https://github.com/BYVoid/OpenCC) (opencc-python-reimplemented) | Apache-2.0 | optional, translation tool only: Simplified to Traditional Chinese drafts |
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0 with a bootloader exception (bundles may be distributed under any licence) | packaging |

## Fonts

| Font | Licence | Used for |
|---|---|---|
| The game's own 3x5 and 5x7 pixel fonts (`engine/render.py`), with accents composed in the same style (`engine/fonts.py`) | the game's licence | Latin text in every EU language |
| [GNU Unifont](https://unifoundry.com/unifont/) (`assets/fonts/unifont.otf`) | SIL OFL 1.1, or GPL-2.0-or-later with the GNU font embedding exception (dual-licensed upstream) | Chinese, Greek, Cyrillic and every character the pixel fonts lack |

Candidates evaluated for Chinese and not bundled (see `docs/spikes/ime.md`): Fusion Pixel Font and
Zpix (both under the SIL OFL 1.1), unreachable from the build environment; they can replace
Unifont later without code changes.

## Translations

The Spanish, Simplified Chinese and Traditional Chinese catalogs (`data/i18n/es.json`,
`zh-Hans.json`, `zh-Hant.json`) are machine drafts: written with an AI assistant, and for
Traditional Chinese converted from Simplified with OpenCC (Taiwan vocabulary). Every entry is
marked `draft` until a native reviewer signs it off (`docs/LOCALISATION.md`). Reviewers will be
credited here by name.
