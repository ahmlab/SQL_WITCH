# Localisation: translating and reviewing SQL Witch

Every word the player reads comes from a catalog, by key. English is the source; every other
language is a file of translations of the same keys.

## Where the text lives

| Text | English source | Key |
|---|---|---|
| Interface, narration, reactions, Codex | `data/i18n/en.json` | as written there (`battle.shatter`) |
| Dialogue, hints, the tutorial's words | `data/story/*.script` | `story.<file>.<node>.<n>` |
| The spell guide (F3) | `data/guide.json` | `guide.<path>` (`guide.examples.3.say`) |
| Lesson titles and key reminders | `data/tutorial.json` | `tutorial.<lesson>.title` / `.keys` / `.hint` |

A translation is `data/i18n/<locale>.json`: one entry per key, plus `_status`, which says for
each entry whether it is a `draft` (machine or unreviewed) or `reviewed`. The languages are
listed in `data/i18n/locales.json`.

`python tools/i18n_report.py export all.json` writes every English string, by key, into one
file: hand it to a translator or a translation service.

## What is never translated

- **SQL**: keywords (`SELECT`, `WHERE`), table and column names (`enemies`, `weakness`,
  `foe_spells`). The player learns the SQL they will use for real.
- **Spell, item and guardian names** (`Healing Herb`, `Ether`, `Sir Wherewell`): they are rows of
  the database, and the player types them in queries. (Decision logged in CLAUDE.md: spell names
  stay English in the database; only the narration around them is translated.)
- **Placeholders** in braces: `{foe}`, `{count}`, `{rows}`, `{player.name}`. Keep them exactly.
- **Inline commands** of the scripts: `{wave}...{/wave}`, `{shake}`, `{color gold}`,
  `{rune WHERE}`, `{pause 300}`. Translate the words between them, keep the commands.

`tools/translate.py` refuses a draft that loses a placeholder or a command, so the game never
shows a broken line.

## Plurals and gender (ICU MessageFormat)

Plurals follow each language's CLDR rules: Polish has `one`, `few`, `many`; Irish has `two`;
Latvian has `zero`. Write every form your language needs:

```
{count, plural, one {# spell fizzles} other {# spells fizzle}}
{count, plural, one {# zaklęcie} few {# zaklęcia} many {# zaklęć} other {# zaklęcia}}
```

The protagonist is feminine or masculine (decision D3, chosen in the character creator; Ada is
the default). Where your language inflects, give both forms with a select on `player.gender`:

```
Bienvenid{player.gender, select, masculine {o} other {a}}, {player.gender, select, masculine {brujo} other {bruja}}.
```

Languages without grammatical gender (Chinese, Indonesian, Hungarian...) simply leave the select
out. `python tools/i18n_report.py` counts, per language, how many entries carry two forms;
`python tools/i18n_report.py lint` points at English lines with he/she/his/her and no select
(most are about someone else, like the Knight, and need nothing).

**The player's name stands alone or in a fixed frame** (`{player.name}:` before a line,
"the heart of {player.name}"), never where your language would decline it.

## Length: every box has a size

Boxes are measured in cells of the 4-pixel text grid; a Chinese character takes two cells.
`data/i18n/boxes.json` gives each key its box (cells and lines); dialogue boxes scroll, so a
long line there is fine. Check a language:

```bash
python tools/i18n_report.py overflow es
```

The tutorial measures its own strip, bubble and checklist; the same command reports those
lines too. The pseudo-locale `qps` (accented, 35% longer) shows which boxes are too small for
the +35% every box is designed for: `python tools/i18n_report.py overflow qps`.

## The workflow

1. **Draft.** `python tools/translate.py --locale fr --from drafts/fr.tsv` imports drafts
   (`key<TAB>text` lines, from a translation service or a person). For Traditional Chinese,
   `--engine opencc --source zh-Hans` converts the Simplified catalog with Taiwan vocabulary.
   Every entry written is marked `draft`; an entry marked `reviewed` is never overwritten.
2. **Review.** A native reviewer edits `data/i18n/<locale>.json` directly (any text editor),
   playing the game with `python main.py --locale fr`, then signs entries off:
   `python tools/translate.py --locale fr --review "story.intro.*"` (globs), or
   `--review "*"` for the whole language.
3. **Check.** `python tools/translate.py --locale fr --check` (placeholders),
   `python tools/i18n_report.py overflow fr` (lengths), `python -m pytest tests/test_i18n.py`.
4. **Ship.** A language appears in the game's language menu (L on the title) once its reviewed
   share reaches `review_threshold` in `data/i18n/locales.json` (100% to start). Until then it
   can be listed in `preview`, where it shows with a "draft" mark: Spanish and both Chinese
   catalogs are there today, as machine drafts waiting for their reviewers.

## Fonts

Text is drawn on the sharp text layer (decision D9). `engine/fonts.py` picks a glyph for each
character: the game's own pixel letters for ASCII; accented Latin letters composed in the same
pixel style from their Unicode decomposition (every EU language, Maltese and Irish included),
plus hand-drawn `ß ł ø æ œ đ ħ ¿ ¡ « » „ “ ” … € –`; and GNU Unifont for everything else
(Chinese, both Simplified and Traditional, Greek, Bulgarian Cyrillic). The tests check that every
character of every catalog can be drawn. A dedicated pixel font for Greek or Cyrillic can be
added to the chain in `engine/fonts.py` without touching the scenes.

## Input

Characters reach the query editor only as text events, so any keyboard layout types `*`, `=`,
`'`, `;`, `<`, `>`, `(`, `)` where it has them. A Chinese input method shows its composition
inline, underlined, until it commits the characters (`TEXTEDITING`, then `TEXTINPUT`). SQL
keywords are ASCII; Chinese only ever appears inside string literals and names the player made.
