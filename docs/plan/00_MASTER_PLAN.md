# SQL Witch — From School Project to Full Game: Master Plan

Version 0.2 · 23 November 2026 (updated the same evening with the team's decisions) · for the three-person team and for the AI sessions that will build it.

This document is the map. Every build prompt in this folder (`01_…` to `13_…`) points back here for
the *why*. When a prompt and this plan disagree, the plan wins; when the plan and the team disagree,
update the plan first, then the prompt.

---

## 1. The thesis (what the game is for)

SQL Witch teaches SQL to people who are afraid that learning is pointless because a machine already
writes queries better than they ever will. The game's answer, delivered through play rather than a
speech: **you will not be the one typing most queries in your life, and you still need to understand
them, because understanding is what lets you direct the machine and build something larger.**

Everything in the full game serves that sentence:

- The **battle system** makes understanding a query the winning skill (the Rule of the Page).
- **Player freedom** (any SQL, including destruction) makes the world feel real and consequences
  real, and turns backups and transactions into something you *want* to learn.
- The **story** shows what data work is for (rows are people), what it costs when it eats a life
  (the protagonist died at a desk), and how to work with a machine instead of against it.
- The **finale** makes the player direct an AI that writes SQL faster than they can, and win by
  reading, correcting and asking the right question.

## 2. Design pillars (the tests every feature must pass)

1. **Queries are the controller.** Every effect in the world comes from a real query run on a real
   database. No fake SQL, no scripted results, no menu that bypasses the Grimoire.
2. **Understanding beats typing.** Mechanics reward reading results, choosing columns, limiting,
   filtering and planning. They never reward speed, and never punish slow thinking.
3. **Freedom with consequences, and a way back.** The player may do anything SQL allows. The world
   reacts in character. A broken world can always be rewound, and rewinding is itself a lesson.
4. **Enemies teach; the Codex remembers.** Runes are no longer locks. A guardian demonstrates a
   technique; the Codex records it; the player uses whatever they already know.
5. **The quest is a party, and the party rests.** Companions, letters from home and the Hearth make
   rest and relationships part of the loop, not a cutscene.
6. **Fun on every keystroke.** Typing a query should feel like casting: sound, light and ink.
7. **Every player, every language.** The game is built for localisation from day one; SQL keywords
   stay in English because that is the SQL the player will use for real.

## 3. Decisions to make before any code (Decision Log)

Each needs an owner and a date. My recommendation is in bold.

| # | Decision | Options | Recommendation and why |
|---|---|---|---|
| D0 | Engine | Stay on pygame-ce; migrate to Godot | **Stay on pygame-ce for Phase 0–1.** `magic/` and `ai/` are engine-free and portable. The engine layer stays thin. Re-decide at the end of Phase 1 with real data: if the target is Steam + consoles, Godot; if PC/itch, pygame ships fine. Known pygame risks to test early: IME input for Chinese names, CJK font rendering, packaging on macOS. |
| D1 | Platforms and store | itch.io; Steam; web; mobile | **itch.io first, Steam second. No web or mobile:** the game is a typing game. |
| D2 | Protagonist — **decided** | Fixed Ada; fully custom; custom look + fixed situation | **Custom name and look, fixed situation.** The protagonist is "the analyst who died at a desk"; the player decides who that was. Ada stays as the default name and canon for marketing. Family and companions are fixed characters: that is where the emotional writing lives. |
| D3 | Gender — **decided** | — | **Selectable in the creator: feminine or masculine.** Every line that inflects (Romance, Slavic, Greek, German, Dutch adjectives/participles) carries an ICU `select` on `player.gender`; writers mark them, the extraction tool counts them, and the budget is known per language. Languages that do not inflect (EN, ZH, ID, HU, FI, ET) carry one form. |
| D4 | Languages at launch — **decided** | — | **Staged.** EN, ES, ZH-Hans **and ZH-Hant** first (the team reviews them; Traditional is not a conversion of Simplified: vocabulary differs, so it is its own catalog). Then the EU-24 + ID through the pipeline with native reviewers per language. |
| D5 | SQL dialect | SQLite only; multi-dialect | **SQLite,** with a Codex page per concept explaining PostgreSQL/MySQL differences. |
| D6 | Licence and ownership (legal work deferred by the team; changing the licence file is still a two-minute task) | CC0 (current); MIT/GPL for code + proprietary assets; all rights reserved | **Change CC0 now.** Code under MIT or GPL-3, story, art and music under a proprietary licence (or CC BY-NC if you want fan content). Decide credits and revenue split among the three of you in writing before the first sale. |
| D7 | Business model | Free; paid; pay-what-you-want | Out of scope for this plan, but it changes D1 and D6. Decide before Phase 2. |
| D8 | AI use in production — **decided** | — | Code and text: AI-drafted, human-approved. **Visual design: entirely generative AI** (backgrounds, portraits, props), with a quantisation and consistency pipeline (prompt 10). Said plainly in the credits: it is the game's own thesis. |
| D9 | Text resolution — **decided** | 1x text; 2x text layer | **Text and UI render at 2x (640×360) over the 320×180 world.** Chinese needs 12–16 px glyphs to be legible; at 1x it is not. Fonts: one Latin/Greek/Cyrillic pixel family at 2x sizes, a CJK pixel font that covers both Simplified and Traditional forms (verify coverage of the Traditional set, not just the common subset), Unifont as the last resort. |
| D9 (revised, 26 Nov 2026) | Resolution — **decided by the author** | 320×180 pixel art; HD | **The canvas is HD, 1280×720 (four real pixels per logical pixel), while every layout stays in the 320×180 grid** (the 36-character page and every box keep their meaning). Art is drawn by code at full resolution (`engine/hd_art.py`); text is HD (JetBrains Mono sized to the grid cell; Unifont for Chinese). `engine/gfx.py` takes logical coordinates (floats: a quarter pixel is one real pixel). |
| D10 | Expert freedom — **decided** | sandbox forbids triggers/indexes; allowed and rewarded | **Allowed and rewarded.** `CREATE TRIGGER` (traps), `CREATE INDEX` (beating the Sage's shuffle), views, transactions: an expert who breaks a guardian with knowledge gets a Trickster reward and a Codex page. Program-safety limits remain (memory, time, file system). |
| D11 | Platforms — **confirmed** | — | **Desktop only** (Windows, macOS, Linux). No web, no mobile, no classroom-management mode. Teachers can put students in front of it; the game gives each player their own statistics (prompt 05). |
| D12 | Defeat — **decided** | — | **Losing restarts the current level** (the battle, from its start, HP/MP restored), unlimited retries, nothing lost; the guardian remembers how many times ("back again?"). Fatigue still rises a little, so a losing streak nudges the player to the Hearth. |
| D13 | Learning philosophy — **decided** | curriculum with drills; learning by interaction | **By interaction only.** No study screens, no quizzes, no drills. A concept is learned by using it, then **recurs** in later guardians, puzzles and minor encounters (the concept map in §5.4). Export of Scrolls as `.sql` and of the world as a real SQLite file is allowed, for players who want to take it home. |

## 4. Architecture for the full game

The school-project architecture holds (the figure "How a foe thinks": Perceive → Decide → Express →
Execute → Reveal, with the intent discarded after Express). The full game adds five systems around it.

```
                   ┌──────────────── engine/ (pygame, thin) ────────────────┐
                   │ scenes · render · animation · grimoire · dialogue UI   │
                   │ textinput · hud · audio (stems) · settings · i18n glue │
                   └───────────────▲──────────────────────▲────────────────┘
                                   │ events                │ reports
  story/  dialogue scripts, ───────┤                       │
  hint director, codex             │                       │
                   ┌───────────────┴───────────────────────┴────────────────┐
                   │ magic/  db · guard v2 (sandbox + snapshots + rewind)    │
                   │         cast · rules · world (integrity + reactions)    │
                   │         fatigue/focus · spellbook (saved queries/views) │
                   ├────────────────────────────────────────────────────────┤
                   │ ai/     brains (FSM, tree, utility, BT, expectimax,     │
                   │         MCTS, N-gram, the Automaton) · styles · roster  │
                   ├────────────────────────────────────────────────────────┤
                   │ i18n/   catalog · ICU messages · fonts · pseudo-locale  │
                   │ save/   slots · autosave · settings · telemetry (opt-in)│
                   │ sim/    headless battles · balance · learning metrics   │
                   └────────────────────────────────────────────────────────┘
```

Hard rules that survive from the school project, now permanent:

1. `magic/`, `ai/`, `story/`, `i18n/`, `save/` never import pygame.
2. One pipeline for player and foe queries.
3. Intent is discarded after Express; only executed queries have effects.
4. One `random.Random` per battle, passed explicitly; visual randomness uses a separate generator.
5. All text the player sees comes from the i18n catalog, by key. No literal UI strings in code.
6. All content (spells, foes, dialogue, hints, reactions, music cues) is data, not code.

### 4.1 Freedom and consequences (the big change)

The battle database is already a private in-memory copy. Phase 0 changes what the sandbox protects:

- **Still forbidden (program safety):** `ATTACH`, `load_extension`, `PRAGMA` that touch the file
  system, non-whitelisted functions, queries over the time budget, more than one statement per cast.
- **Now allowed (world freedom):** `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE TABLE/VIEW`,
  `ALTER`, `BEGIN/SAVEPOINT/ROLLBACK`, `UNION` and friends.
- **Snapshots:** the engine takes a snapshot of the whole database before every player query
  (SQLite backup API or `savepoint`). The Grimoire has a **Rewind** page: the player can go back to
  any snapshot. Rewinding costs a turn, so it is a decision, not an undo button.
- **Integrity check:** after every query the world module classifies the state: *intact*, *altered*
  (data changed), *damaged* (a table the fight needs is gone or empty), *broken* (the engine cannot
  continue). Each class has reactions.
- **Reactions** live in `data/reactions.json`: a pattern (which table, which change) → who speaks,
  what they say, and what the world does. Examples: player drops `spells` → the foe laughs and
  attacks every turn until the player rewinds; player drops `foe_spells` → the foe forgets its
  spells and stands there; player deletes the foe's row → the fight ends in confusion, no reward,
  the Codex records "you may want to learn about backups"; player inserts a spell named like a
  foe's spell → the engine refuses at the name-uniqueness check, in character.
- **Brains survive anything.** Every brain receives a possibly broken `BattleState` and must return
  a legal intent or a `Confused` intent (rendered as the foe staring at an empty book).

### 4.2 Runes become the Codex

The rune gate is removed from `guard.inspect`. `inspect` still returns the technique signature;
that signature now feeds three things: the Codex (first use of a technique unlocks its page, with
the guardian's example), the Hint Director (what the player has and has not tried), and the
player model (NULL and difficulty adaptation). Guardians still *demonstrate* their technique; if
the player already uses it, the guardian acknowledges it in dialogue instead of teaching it.

### 4.3 Turn discipline

The editor is read-only unless the battle phase is `input` and it is the player's turn. The closed
Grimoire is drawn differently and says why. Queued keystrokes are dropped, not buffered.

### 4.4 Saved queries are views

After a query has been cast successfully three times (the memorisation threshold, tunable), the
player may save it as a **Scroll**. A Scroll is literally a `CREATE VIEW` in the battle database,
so casting a Scroll is `SELECT * FROM scroll_name`. Scrolls persist in the save file, can be renamed,
edited and parameterised later (`{foe}`), and the Codex explains that this is what a view is.

### 4.5 Fatigue and Focus (rest as a mechanic)

A single meter. Casting, fighting and skipping rest raise **Fatigue**; resting at the Hearth, sleeping
and reading letters lower it. Fatigue shrinks the page (`PAGE_ROWS` 4 → 3 → 2) and blurs the result
text. Efficient casts (no overflow, no fizzle) build **Focus**, which temporarily widens the page.
A tired witch reads fewer rows: the theme, as a rule the player can feel.

## 5. Content plan

### 5.1 Story in three acts

**Act 1 — Reading the world.** The protagonist dies at a desk (overwork, a report nobody read) and
wakes in Codd, where every living thing is a row. The regions' problems are real analyst problems in
costume: a village whose harvest records are unreadable (SELECT/LIMIT), a keep that filters refugees
badly (WHERE), a library in disorder (ORDER BY), two archives that cannot match their people (JOIN), a
barracks that cannot count its dead (GROUP BY), a crypt where the answer is inside another answer
(subqueries). Each solved problem shows lives improved by data. The party forms: companions with jobs
and families, who go home at night.

**Act 2 — Changing the world.** The protagonist learns that reading is not enough. Guardians teach
INSERT (bringing records, and people, back), UPDATE (correcting a wrong that has stood for years),
DELETE (letting go, carefully), transactions and backups (the Chronomancer: nothing is lost if you
saved it), views and constraints (building something others can rely on). The Hearth matters here:
Fatigue is real, letters from home arrive, and a companion burns out if the party never rests.

**Act 3 — The machine.** The **Automaton** appears: it writes perfect SQL instantly and offers to write
the protagonist's spells. Used blindly, its queries drift (wrong column, wrong table, right syntax)
and the fight goes wrong. Used well, read and corrected, it is the strongest ally in the game.
**NULL**, the voice of doubt ("why learn, the machine knows"), is the final guardian; the final
battle is the protagonist directing the Automaton against NULL. The ending: the protagonist is sent
back (or chooses to stay) understanding what their work was for and what rest is for.

### 5.2 Guardian roster (concept → boss → AI brain)

| Act | Concept | Guardian | Brain (from the design doc) |
|---|---|---|---|
| 1 | SELECT/FROM | Training Dummy (tutorial) | scripted |
| 1 | LIMIT | Asterisk Slime | probabilistic FSM |
| 1 | WHERE | Sir Wherewell | decision tree, stochastic leaves |
| 1 | ORDER BY | Sorting Sage | utility + softmax |
| 1 | JOIN | Twin Archivists | expectimax |
| 1 | GROUP BY/HAVING | Count Aggregor | behaviour tree |
| 1 | subqueries | Nested Lich | MCTS |
| 2 | INSERT | The Gravedigger (summons rows; you insert allies) | behaviour tree |
| 2 | UPDATE | The Cursed Scribe (wrong facts in stone) | utility |
| 2 | DELETE | The Hoarder (a plague of rows) | FSM + planning |
| 2 | transactions/backups | The Chronomancer | MCTS over snapshots |
| 2 | views/constraints | The Architect | expectimax |
| 3 | directing an AI | The Automaton (ally and trial) | an LLM-free "perfect" query generator with drift |
| 3 | IS NULL/COALESCE | NULL, the Voice of Doubt | N-gram player model |

### 5.3 Practice between guardians (the missing middle)

Guardians are lessons; practice is everything between them. All of it is play, never study:

- **Minor encounters ("wild rows")** on the walk: one or two turns, each built around one technique
  the region has already taught or is about to (a swarm that only GROUP BY clears; a mimic that
  only dies when targeted by name; a moth that hides unless you ORDER BY). They respawn with new
  seeds, so the same technique is used again on a different table.
- **Scrying puzzles** in the world: which chest holds the key, which door is real, which path is
  safe, answered by a query against a local table; wrong answers cost Fatigue, never progress.
- **Riddle gates:** a troll, a gate or a statue asks a question whose answer is a number or a name
  the player must compute (`COUNT`, `MAX`, a filtered row). Zelda's locked doors, with SQL as the key.
- **Villager requests:** real analyst tasks in costume (the family whose harvest is below the
  average; the patient whose record is duplicated; the shipment that never arrived). Rewards: items,
  Scroll slots, letters.
- **Cloze locks:** a query carved in stone with one blank; the player completes it. The cheapest way
  to make a technique recur without a fight.
- **Hearth cooking:** recipes are a JOIN between `recipes` and the pantry; cooking well lowers
  Fatigue more.
- **Query golf with companions:** a companion challenges the player to reach the same result with
  fewer rows or less MP; it teaches precision and is the main replay hook.
- **The Dummy's challenge board:** the Training Dummy returns in every region with a seeded daily
  challenge (a small table and a goal), the place to try anything with no stakes.
- **Trickster goals:** optional, hidden until found: break a guardian in a specific clever way
  (trap the Gravedigger with a trigger; index the Sage; roll back the Chronomancer's own turn).

### 5.4 Concept map (how techniques recur)

Every concept has: the guardian that demonstrates it, two minor encounters that require it in the
following region, one puzzle that combines it with the previous concept, and one later guardian
whose fight is easier with it. The content build (prompt 09) and the practice loop (prompt 08)
check this map, so nothing is taught once and forgotten. The map lives in `data/concepts.json`,
with the real-world counterpart of each concept for the Codex.

### 5.5 Systems list (complete)

Character creator (with layered portraits) · sprite animation · dialogue engine · hint director (talking guardians and
Grimoire) · Codex · freedom/consequences/rewind · turn lock · Scrolls (saved queries) · Fatigue/Focus ·
Hearth (rest, letters, companions) · items and exploration levers · world map · save profiles, slots and
autosave · player statistics screen · settings, fullscreen and accessibility · i18n (27 languages, fonts, IME) · adaptive music (stems) ·
background layer system · juice/feel pass · packaging and CI · telemetry and learning metrics.

## 6. Roadmap (phases, not dates: three part-time people)

**Phase 0 — Foundations (engineering, no new content).** Prompts 01–06. Repository reset,
freedom and consequences, turn lock, dialogue engine, i18n core with EN/ES/ZH, save and settings,
character creator and animation. Exit criterion: the existing game (tutorial, Slime, Knight) runs on the new foundations in
three languages, with a custom animated protagonist, and all tests pass.

**Phase 1 — Vertical slice of the full game.** Prompts 07, 08, 10, 11, 12. Act 1 region 1 with everything:
story, Hearth, companions, new backgrounds, adaptive music, Scrolls, Fatigue, the item/exploration
levers, juice pass. Exit criterion: 10 strangers play 30 minutes; they rest at the Hearth on their
own, open the satchel on their own, and can say what a data analyst does.

**Phase 2 — Content.** Prompt 09 plus the story scripts. Acts 1–3, all guardians, all regions, the Automaton and NULL. Exit criterion:
a complete playthrough, balanced by the simulator, in EN/ES/ZH.

**Phase 3 — Localisation, polish, launch.** Prompt 04's staged rollout (EU-24 + ZH-Hant + ID with
native review), accessibility pass, packaging, store pages, a launch trailer. Prompt 13 is run at
every phase exit and closes this one.

Rough effort for three part-time people: Phase 0 ≈ 6–8 weeks, Phase 1 ≈ 8–10 weeks, Phase 2 ≈ 4–6
months, Phase 3 ≈ 2–3 months. If that is too long, cut Act 2 to three guardians before cutting
anything else.

## 7. Risks (and what to do about each)

| Risk | Mitigation |
|---|---|
| 27 languages, unreviewed | Staged launch (D4); pseudo-localisation tests; a reviewer per language before it is enabled. |
| Chinese illegible at 320×180 | D9: 2x text layer; glyph coverage test for Simplified and Traditional; both catalogs reviewed by the team. |
| Generative art that does not match itself | Prompt 10: a style anchor set, palette quantisation to 32 colours, per-layer generation with masks, and a consistency check before any image enters the game. Sprites stay pixel-tool made: generators are bad at sprite sheets. |
| Freedom lets an expert hang the game | Memory limits (`max_page_count`, `setlimit`), recursion depth, time budget; triggers run inside the same budget. |
| Selectable gender raises translation cost | D3 decided: two forms per inflecting language, marked by writers, counted by the extraction tool; the writing style still avoids inflected forms where it can. |
| Chinese typing in pygame | Spike it in Phase 0 week 1: IME events, a CJK pixel font, name entry. If it fails, D0 is re-opened immediately. |
| Freedom breaks the AI | Every brain tested against every damaged-state class; `Confused` intent; integrity check before Decide. |
| Rewind becomes an undo button | Rewind costs a turn and is logged; some reactions are permanent until the Hearth. |
| Blank protagonist weakens the family theme | Fixed family and companions carry the arc; the protagonist's letters are written in second person. |
| Scope: a castle with forty towers | Phase exit criteria are the gate. Nothing from Phase 2 starts before Phase 1's playtest. |
| pygame on macOS / packaging | Packaging in CI from Phase 0, on all three platforms, every week. |
| Learning claims without evidence | Telemetry opt-in from Phase 1; the same learning metric as the school report (technique use before/after its guardian). |

## 8. How to work with the AI builder (process rules that worked)

1. One workstream per session, in the order of this folder. Start every session with the prompt
   file, after updating `CLAUDE.md` (prompt 01 rewrites it).
2. Every prompt begins with **read and report** and ends with **tests I expect**. The builder stops
   after each numbered step and waits for approval. It never runs git.
3. Anything with a voice (story, dialogue, hints, reactions) is produced as a data file first and
   edited by a human before it is wired in. The team's voice is the game's voice.
4. Every feature ships with its data file, its tests, and a paragraph in `docs/` explaining how a
   non-programmer changes it.
5. Playtest at every phase exit. The playtest protocol from the school project stays.
