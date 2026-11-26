# Prompt 08 — Hearth, Fatigue/Focus, items, the practice loop (puzzles and minor encounters), world map

Read `docs/plan/00_MASTER_PLAN.md` §4.5, pillar 5, and the signed-off `docs/story/` documents.
This prompt builds the systems that make rest, family and exploration part of play.

---

## 0. Read and report

Read `magic/cast.py` (PAGE_ROWS), `magic/battle.py`, `magic/world.py`, the save format, the
dialogue engine, and `data/items.csv`. Report in 15 lines how you will attach Fatigue to the page
size, where the Hearth sits in the flow, and the exploration levers you will build. Stop and wait.

## 1. Fatigue and Focus (`magic/fatigue.py`, tunables in `data/fatigue.json`)

- One meter from 0 to 1. Rises per battle round, per cast, and per region travelled; falls at the
  Hearth (sleep: full reset; a meal: partial; reading a letter: a little, and a Focus bonus).
- Effects, by band: page rows 4 → 3 → 2; result text drawn "blurred" (a pixel jitter, reduced
  motion aware); the Grimoire yawns in dialogue; companions comment; at the top band the
  protagonist faints at the end of the battle regardless of outcome and wakes at the Hearth.
- Focus: consecutive efficient casts (no overflow, no fizzle, no miscast) raise a short-lived
  bonus that adds a page row; any sloppy cast resets it. Shown as a glow on the page edge.
- Everything observable in the HUD; everything in the save.

## 2. The Hearth (`engine/scenes.py` HearthScene, data in `data/hearth/`)

- A camp or home scene between regions with: sleep, cook (a small recipe table the player queries
  to choose a meal: items are rows), talk to each companion (dialogue nodes with conditions on
  story variables and Fatigue), the mirror (character look), the Scroll shelf (manage Scrolls), the
  letter box (family letters arrive by story progress), the map table, a named **world backup**
  (saves a snapshot of the world database the Chronomancer fight will use).
- Leaving the Hearth without sleeping is allowed; the companions notice.

## 3. Items and exploration levers

Players beat the school build by attacking only. Build these, each tunable in data:

- **Pressure:** two guardians in Act 1 cannot be won by damage alone (one needs a ward or heal to
  survive a telegraphed big turn; one has a phase where attacks fizzle and only an item works).
  Use the simulator to target a 60–75% first-attempt win rate per guardian for the Competent bot.
- **Discovery:** the first free look at each table in a battle grants a small Insight reward (MP,
  a Codex line); the satchel pulses when HP is low and an item would help; guardians taunt about
  unopened satchels (prompt 03 pools).
- **Hearth quests:** short tasks that require reading tables ("find the villager whose harvest is
  below the average") with rewards; three per region.
- **Item design:** items are rows with kinds (hp, mp, ward, cleanse, scry-boost, snapshot-charm:
  a free extra snapshot). Drops come from guardians and quests; shops are queries (`SELECT name,
  price FROM stall`), buying is an `INSERT INTO items … SELECT …` the shopkeeper writes with you,
  which also teaches INSERT … SELECT before Act 2.

## 4. The practice loop (plan §5.3–5.4)

Build the systems, with one example of each in Act 1 region 1, all data-driven:

- **Minor encounters** (`data/encounters/*.json`): 1–2 turn fights using the full battle pipeline
  with a reduced HUD, seeded per visit, each tagged with the concept it exercises; the encounter
  table per region respects the concept map (`data/concepts.json`).
- **Scrying puzzles and riddle gates** (`data/puzzles/*.json`): a local table, a goal (a value, a
  row, a set), a check on the query *result*, hints through the Hint Director, Fatigue cost on a
  wrong answer, never a lock on progress.
- **Cloze locks:** a query with one blank, completed in the Grimoire editor; checked by result.
- **Villager requests** and **query golf** with companions (fewer rows or less MP for the same
  result; the companion's own query is shown afterwards as the Codex example).
- **The Dummy's challenge board:** a seeded daily table and goal, no stakes, in every region.
- **Trickster goals:** read from `data/tricks.json` (prompt 02) and shown as hidden entries.
- A `concepts.json` validator fails the build if any concept lacks its recurrences.

## 5. World map (`engine/scenes.py` MapScene)

The map from the design doc: regions as nodes, a walk between them with signposts (lore and
quest hints), the party drawn with the walk animation, time of day and Fatigue affecting the
palette. Act 2 branching per the outline. Fast travel from the Hearth once a region is cleared.

## Tests I expect

- Fatigue bands change `PAGE_ROWS` in a cast report; Focus adds a row only after N clean casts
  and resets on a fizzle; faint at the top band ends the battle correctly.
- Hearth actions change Fatigue by the data values; letters arrive on the right story flags;
  the world backup is restorable.
- Simulator: each Act 1 guardian within the target win band for Competent; the attack-only bot
  loses to the two pressure guardians more than 60% of the time.
- Insight triggers once per table per battle; the shop INSERT goes through the pipeline and name
  uniqueness.
- Map: regions unlock in order; fast travel only to cleared regions; the save records position.
- Puzzles pass by result with at least two different valid queries; a wrong answer costs Fatigue
  and never blocks; minor encounters are seeded and tagged; the concept validator catches a
  concept with no recurrence; query golf scores by rows and MP, never by time.
