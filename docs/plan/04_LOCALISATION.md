# Prompt 04 — Localisation: 27 languages, fonts, input, pipeline

Read `docs/plan/00_MASTER_PLAN.md` decisions D3–D5 and risk table, plus `docs/spikes/ime.md`.
Target languages: English, Chinese Simplified **and** Traditional (both at launch, separate
catalogs: vocabulary differs), Indonesian, and all
24 official EU languages (Bulgarian, Croatian, Czech, Danish, Dutch, Estonian, Finnish, French,
German, Greek, Hungarian, Irish, Italian, Latvian, Lithuanian, Maltese, Polish, Portuguese,
Romanian, Slovak, Slovenian, Spanish, Swedish). SQL keywords, table and column names stay in
English everywhere, by design: that is the SQL the player will use for real.

---

## 0. Read and report

Read how text reaches the screen today (`engine/render.py`, `engine/dialogue.py`, the HUD, the
Grimoire status line, the tutorial), and the script format from prompt 03. Report in 15 lines: how
many distinct user-visible strings exist, where they live, which fonts are used, and your plan for
plural and gender handling. Stop and wait.

## 1. Catalog and message format (`i18n/`)

- One source catalog per language in `data/i18n/<locale>.json`, keyed by stable ids; English is
  the source of truth. Use ICU MessageFormat for plurals and gender (`{count, plural, one {…}
  other {…}}`, `{gender, select, …}`), because Polish, Czech, Irish, Lithuanian and others have
  plural rules English does not. Pick a maintained ICU library or implement the subset needed and
  test it against CLDR plural rules for every target language.
- `t(key, **args)` is the only way to get text; it falls back to English and logs a missing key
  once. A lint fails the build on literal user-facing strings outside the catalog.
- Extraction: a tool that pulls source strings from `data/story/*.script`, `data/hints.json`,
  `data/reactions.json`, `data/codex.json`, `data/tutorial.json` and code keys into the English
  catalog, and reports untranslated keys per language.
- Numbers, dates and lists use locale formatting (`20 PM` vs `20 PM`, decimal separators, the
  status line `11 rows | 4 cast`).

## 2. Fonts and rendering

- Text renders on the **2x layer** (D9: 640×360 over the 320×180 world), so CJK glyphs are
  12–16 px. A font service with a fallback chain per script: Latin extended (covers EU diacritics
  incl. Maltese and Irish), Greek, Cyrillic (Bulgarian), CJK with verified coverage of both
  Simplified and Traditional forms (test every character used by both catalogs against the font),
  with GNU Unifont as the last resort. All at pixel sizes designed for the 2x layer; document each font's licence in
  `CREDITS.md`. Text that mixes scripts (a Chinese name inside an English UI) renders per run.
- Text expansion: UI boxes are designed for +35% over English; a test renders every catalog string
  of every language into its target box and fails on overflow.
- Pseudo-localisation locale (`qps`): lengthens strings and replaces letters with accented ones,
  to catch hard-coded text and overflow early. CI runs the game's scripted playthrough in `qps`.

## 3. Input

- Chinese names: IME composition (`TEXTEDITING`) shown inline in the name field and in the
  Grimoire editor (players may name Scrolls in Chinese). Non-ASCII in queries only ever appears
  inside string literals and identifiers the player created; SQL keywords are ASCII.
- Keyboard layouts: the query editor must not assume US layout for `*`, `=`, `'`, `;`, `<`, `>`,
  `(`, `)`. Use text input events for characters, key events only for editing keys.

## 4. Gender (Decision D3: feminine or masculine, chosen in the creator)

Every source line about the protagonist that inflects in the target languages carries an ICU
`select` on `player.gender` with both forms. The extraction tool reports, per language, how many
entries need two forms; a lint warns on English lines that look like they will inflect and lack
the marker. The player's name is never placed where the language would decline it (Polish,
Czech, Finnish, Hungarian): the writing rule is "the name stands alone or in a fixed frame".

## 5. Translation pipeline

- `tools/translate.py` produces a machine draft for a locale from the English catalog, marks every
  entry `draft`, and never overwrites a `reviewed` entry. A locale is listed in the language menu
  only when its reviewed ratio is above a threshold (start: 100% for EN/ES/ZH, which the team
  reviews; the rest stay hidden until a native reviewer signs off).
- `docs/LOCALISATION.md` for reviewers: how to edit a catalog, what must not be translated (SQL,
  table names, spell names? decide: spell names are translatable, table and column names are not),
  how to run the overflow test.

## Tests I expect

- CLDR plural categories for all 27 locales; ICU `select` for gender.
- Every key used in code or data exists in English; `qps` playthrough shows no untranslated text.
- Overflow test across all enabled locales; mixed-script rendering test; IME composition test
  with synthetic `TEXTEDITING` events; glyph coverage test for the ZH-Hans and ZH-Hant catalogs.
- Language switch at runtime re-renders every open scene without restart.
