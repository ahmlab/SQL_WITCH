# Prompt 03 — Dialogue engine, text pacing, talking guardians and the Hint Director

Read `docs/plan/00_MASTER_PLAN.md` §2 pillars 4–6 and `CLAUDE.md`. The current conversations
feel empty and too direct, and the typewriter pace is wrong. This prompt builds the system that
writers will use for the whole game; the writing itself comes later (prompt 07), by humans.

---

## 0. Read and report

Read `engine/scenes.py` (DialogueScene, narration beats), `data/dialogue.json`,
`data/tutorial.json`, `data/guide.json`, `engine/guide.py`, `engine/textinput.py`
(the guided typing and hint escalation from the tutorial), and the audio events. Report in 15
lines how dialogue is driven today, what the typewriter does, and how you would replace it without
breaking the tutorial. Stop and wait.

## 1. The script format (`story/script.py`, files under `data/story/*.script`)

A plain-text screenplay format writers can edit without escaping JSON. Design it, document it in
`docs/WRITING.md`, and give it a parser with clear errors (file, line, what is wrong). Required
features:

- Nodes with ids (`== glade_intro ==`), lines as `speaker: text`, stage directions in brackets
  (`[portrait ada sad]`, `[music hearth]`, `[sfx book]`, `[shake]`, `[wait 400]`).
- Inline pacing: `{speed fast}`, `{speed slow}`, `{pause 300}`, `{instant}`; a default
  characters-per-second per speaker and per language (CJK needs a slower default per character).
- Inline effects: `{wave}…{/wave}`, `{shake}…{/shake}`, `{color gold}…{/color}`, rune highlight
  `{rune WHERE}`.
- Choices (`-> text => node_id`), conditions (`<<if codex.WHERE>>`, `<<if integrity == damaged>>`,
  `<<if fatigue > 0.7>>`), variables (`<<set met_sage = true>>`), jumps, and `[end]`.
- Every line has a stable **i18n key** derived from node id + line index, and the English text in
  the script is the source string for the catalog (prompt 04 extracts it).
- Skip (hold a key to fast-forward), a dialogue log the player can reopen, auto-advance option.
- Portraits with emotions, per-speaker voice blips (reuse the typing-note idea: each speaker has a
  pitch and a timbre), text box styles per speaker (Grimoire, guardian, companion, letter).

## 2. Text rendering (`engine/dialogue.py`)

- Word wrap that measures with the real font and handles CJK (wrap by character, respect
  no-break rules for punctuation), Latin with hyphenation off, and text expansion (a box that
  cannot fit a translated line scrolls inside its box rather than overflowing; a test catches it).
- Typewriter driven by the script pacing, not by frame count; pauses on punctuation
  (`,` short, `.` longer) configurable per language in `data/pacing.json`.
- Font fallback chain (prompt 04 supplies fonts): the renderer asks the i18n font service for the
  right font per character run.

## 3. Talking guardians and the Grimoire (`story/hints.py`, data in `data/hints.json`)

The **Hint Director** watches a battle and decides when someone should speak during the
player's turn. It is pygame-free and unit-tested.

- Signals: idle seconds, consecutive miscasts, overflow count, HP ratio, MP ratio, techniques the
  player has never used (from the technique signatures), items never opened, integrity class, the
  brain's `explain()` (so taunts are truthful: "I can see every spell in that book of yours").
- Speakers: the guardian (in character, with a taunt that contains a real hint, chosen from its
  own hint pool) and the Grimoire (gentle, explicit). The guardian speaks first; the Grimoire steps
  in if the player is still stuck. Companions can speak from the sidelines in Phase 1.
- Rules: at most one line per turn; cooldowns; never the same line twice in a fight; escalating
  specificity (observation → nudge → a concrete query shape → an offer to show the exact query);
  silence when the player is doing well. Thresholds in the data file.
- Every hint line is a script node, so it uses the same format, effects, portraits and i18n keys.
- Write pools for the Slime, the Knight and the Grimoire: 8 guardian lines each, 12 Grimoire
  lines, covering: never looked at `enemies`, never opened `items`, overflowing twice, low HP
  with an unused heal, low MP with an unused Ether, a locked-in habit (same query 3 turns),
  a damaged world ("you broke my table, little witch; do you know how to put it back?").

## 4. Migrate what exists

Port `data/dialogue.json` and the tutorial's lines to the new script format without changing
their content. The tutorial scene keeps working.

## Tests I expect

- Parser round-trips a sample script; malformed input reports file and line.
- Pacing: a line with `{pause}` takes measurably longer in simulated time; CJK default speed
  differs from Latin.
- Wrapping: a 50-character German line fits the box; a CJK line wraps by character; an overlong
  line never draws outside its box.
- Hint Director: scripted battles produce the expected line at the expected turn; cooldowns and
  no-repeat hold; a strong player gets silence; the guardian's taunt matches its `explain()`.
- Every hint and dialogue line has a unique i18n key.
