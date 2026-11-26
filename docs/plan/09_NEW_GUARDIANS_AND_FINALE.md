# Prompt 09 — Act 2 and Act 3 guardians: write, change, back up, build, direct

Read `docs/plan/00_MASTER_PLAN.md` §5.2 and `docs/story/05_automaton_and_null.md`. Every guardian
keeps the five-stage loop (Perceive → Decide → Express → Execute → Reveal), one brain, one SQL
style, one lesson, and must be beatable by its own concept. Build them **one at a time**, each
with its brain tests, style tests, simulator run and Hint Director pool, and stop after each.

---

## 0. Read and report

Read `ai/`, `magic/world.py` (reactions, snapshots), `magic/spellbook.py`, `sim/`, and the roster.
Report in 15 lines how write-kind queries flow through `cast.resolve` today and what the casting
contract needs for `INSERT`/`UPDATE`/`DELETE` effects. Stop and wait.

## 1. Extend the casting contract for writes (`magic/cast.py`)

- A write query has effects by what it changed, not by names in a result: inserting a row into
  `allies` summons; updating `enemies.weakness` is a hex (the world checks it and may refuse for
  guardians with `weakness_locked`); deleting rows from the foe's summon table banishes; a
  transaction block resolves as one cast with one MP cost and one snapshot.
- MP cost for writes: rows affected × a per-kind cost, capped by the page (the Rule of the Page
  still applies: you can only affect as many rows as you can read back). Every write echoes its
  affected rows onto the page so the rule stays visible.

## 2. The guardians

| Guardian | Concept | Mechanic sketch | Brain |
|---|---|---|---|
| The Gravedigger | INSERT | Raises minions from a `graves` table each turn; the player wins by inserting allies into `allies` from `villagers` rows (`INSERT … SELECT`) who then fight; the foe's style: `INSERT INTO minions SELECT … FROM graves …`. | behaviour tree |
| The Cursed Scribe | UPDATE | Its stone tablets (`decrees`) hold wrong facts that buff it; the player corrects rows with UPDATE (and must read first to know what is wrong); it rewrites them back on its turn. | utility + softmax |
| The Hoarder | DELETE | Fills `clutter` with rows that absorb spells; the player deletes with precise WHERE (deleting too much hurts: some rows are villagers' belongings, a `DELETE` without WHERE is a tragedy with a reaction). | FSM with a planner for what to hoard |
| The Chronomancer | transactions and backups | Rewrites the world each turn; the player's defence is `SAVEPOINT`/`ROLLBACK` and the Hearth backup; victory requires restoring a state the foe never saw. | MCTS over snapshots |
| The Architect | views and constraints | Rebuilds its fortress from a `CREATE VIEW`; the player wins by creating a better view and a `UNIQUE` constraint the foe trips on. | expectimax |
| The Automaton | directing an AI | See step 3. | the drifting generator |
| NULL | IS NULL/COALESCE + the run's habits | From the design doc, now reading the whole run. | N-gram |

For each: foe rows and spells in data, a style grammar, a hint pool, a Codex page with the real-
world counterpart (what an analyst does with this concept), a reaction set and a **trick set**
(D10) for the ways a player can break the fight, and its entry in `data/concepts.json` with the
earlier concepts it recurs (every Act 2 fight is easier with at least two Act 1 techniques).

## 3. The Automaton (ally and trial)

- A **generator** (no network, no LLM) that produces a syntactically perfect query for an
  intent the player asks for, with **drift**: one semantic slip (wrong column, wrong table, off-by-
  one in a comparison, a missing join condition) with probability `drift_rate` that drops as the
  player corrects its output. It never produces forbidden SQL.
- The player interface: the Grimoire gains an "ask the Automaton" page: pick a shape (filter,
  sort, join, aggregate, write) and a target; the draft appears in the editor **for editing**;
  casting it unedited is allowed and is how the trial fight punishes blind trust.
- As a trial: the fight where it first appears is won only by catching drift. As an ally: from
  then on it is available in every fight, with its drift rate persisted and visible.
- The finale: directing it against NULL, with NULL's lines built from the player's real
  statistics from `query_log`.

## 4. Balance and evidence

- Simulator bots gain write skills (Competent and Expert write transactions; Novice does not).
- Per guardian: win-rate bands, battle length, action entropy and mutual information (the school
  metrics), and the "concept required" check: the attack-only bot must lose.

## Tests I expect

- Write-contract tests per statement kind; MP for writes follows rows affected and the page cap.
- Each brain legal and non-deterministic, survives every damaged state, beats RandomBrain.
- Automaton: drift rate and kinds as configured; unedited drafted queries cast through the real
  pipeline; a corrected draft lowers the rate; it never emits forbidden SQL.
- NULL's lines reference true counts from the log fixture.
- Simulator bands met for all Act 2–3 guardians.
