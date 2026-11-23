# Prompt 02 — Freedom, consequences and Rewind (sandbox v2), Runes → Codex, turn lock

Read `docs/plan/00_MASTER_PLAN.md` §4.1–4.3 and `CLAUDE.md` first. This is the largest change to
the core; it touches `magic/guard.py`, `magic/cast.py`, `magic/battle.py`, every brain, the roster
and the Grimoire.

---

## 0. Read and report

Read `magic/`, `ai/`, `engine/grimoire.py`, `engine/scenes.py` (battle phases), `tests/test_exploits.py`,
`tests/test_sandbox.py`, `tests/test_brains.py`. Report in 20 lines: how you will split the sandbox
into *program safety* and *world freedom*, how snapshots will work (SQLite backup API vs
`SAVEPOINT`, with the trade-offs), and which existing tests will be deleted because they assert the
old locks. Stop and wait.

## 1. Sandbox v2 (`magic/guard.py`)

- Keep: single statement per cast (except an explicit `BEGIN … COMMIT` block, see below), the time
  budget, the function whitelist (extend it with `length`, `lower`, `upper`, `substr`, `replace`,
  `typeof`, `random` is **not** allowed), denial of `ATTACH`, `DETACH`, `load_extension`, any PRAGMA
  that reads or writes the file system, and `VACUUM`.
- Allow: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE TABLE`, `CREATE VIEW`, `CREATE INDEX`,
  `CREATE TRIGGER`, `ALTER`, `UNION`, `EXCEPT`, `INTERSECT`, `WITH` (incl. `RECURSIVE`), `BEGIN`,
  `SAVEPOINT`, `RELEASE`, `ROLLBACK`, `COMMIT`. Decision D10: experts are free.
- Program-safety limits that make that freedom safe: `PRAGMA max_page_count` sized for the battle
  database, `conn.setlimit` for SQL length, compound selects, expression depth, trigger depth and
  `LIKE` pattern length; recursion capped; `zeroblob`/`randomblob` not whitelisted; triggers fire
  inside the same time budget as the query that caused them.
- The forgery ward stays for `SELECT` lists (names must be read, not typed), but an `INSERT` may of
  course contain literals: that is how the player brings things into the world. Name uniqueness
  across all tables is enforced on insert, in character.
- `inspect()` keeps returning the technique signature and gains `kind`: `read`, `write`, `schema`,
  `transaction`.
- Delete the rune gate. Keep `Miscast` and the in-character refusal lines for what is still refused.

## 2. Snapshots and Rewind (`magic/world.py`)

- Before every player query that is not a free look, snapshot the database (choose the mechanism
  from step 0; it must be cheap at this size and must capture schema changes).
- `Rewind` is a Grimoire page listing snapshots by turn with a one-line summary of what changed
  after each ("turn 3: you dropped `spells`"). Rewinding restores the database **and the battle
  state**, costs the player's turn, is logged to `query_log`, and the guardian comments on it.
- Snapshots are per battle. At the Hearth (later prompt) the player can also save a named backup
  of the world; the Chronomancer fight builds on this.

## 3. Integrity check and reactions

- After every query (player or foe): classify the world as `intact`, `altered`, `damaged`,
  `broken` using a declarative list of what a battle needs (`witch` row, `spells` with ≥1 castable
  row, the foe's row, `foe_spells`, `type_chart`).
- `data/reactions.json`: entries with `when` (table, change kind, actor), `speaker`, `line_key`,
  `effect` (one of: `foe_rages`, `foe_forgets`, `fight_ends_confused`, `codex_unlock`, `none`),
  `cooldown`. Write the first 15 reactions covering: dropping/emptying each core table by the
  player, deleting the foe's row, deleting the witch's row (the Grimoire refuses: "you are not a row
  I will let you delete"), inserting a spell with a foe's spell name, renaming a column the foe
  needs, creating a table named like a core one, a `ROLLBACK` with no transaction, a `COMMIT`.
  Lines go through i18n keys; the English text lives in the catalog, not in the JSON.
- Permanent consequences: a `broken` world that the player does not rewind ends the battle with
  no reward and a Codex entry on backups.
- **Trickster rewards (D10).** Breaking a guardian *with knowledge* is a win, not a bug: a trap
  trigger that fires on the foe's insert, an index that defeats the Sage's shuffle, a view the foe
  reads, a rollback of the foe's own turn. `data/tricks.json` lists each recognised trick (pattern
  on the log plus resulting state), its reward (a Scroll slot, an item, a Codex "Trickster" page,
  an achievement) and the guardian's line. Unrecognised breaks still get the confused ending; the
  log is reviewed after playtests to add new tricks.

## 4. Brains survive anything (`ai/`)

- `BattleState` gains `integrity` and `missing` fields. Every brain must return a legal intent or
  `Intent.confused()` for any state. Add a `ConfusedStyle` rendering: the foe's book shows an empty
  page or `SELECT * FROM a_table_that_was_here`, which miscasts in character.
- The foe never gets stronger from damage the player did to the foe, only from damage to the
  player's side (`foe_rages`).

## 5. Runes become the Codex (`story/codex.py`, data in `data/codex.json`)

- First use of a technique signature unlocks its Codex page: a short explanation, the guardian's
  example query, the SQLite vs PostgreSQL/MySQL note, and the player's own first query (recorded).
- Guardians still demonstrate; if the player has already used the technique, the roster marks the
  Invitation as "acknowledged" and the dialogue branches (hook for prompt 03).

## 6. Turn lock (`engine/scenes.py`, `engine/textinput.py`)

- The editor accepts input only in phase `input` on the player's turn. Otherwise it is drawn as a
  closed book with a one-line reason key (`ui.book_closed.foe_turn`, `ui.book_closed.animating`).
- Keystrokes during a closed phase are dropped, with one soft sound, never buffered.
- `--start` into any battle begins with the correct phase; the first frame is never editable if
  the foe opens.

## 7. Spellbook: Scrolls as views (`magic/spellbook.py`)

- A query cast successfully `SCROLL_THRESHOLD` (3) times may be saved as a Scroll: `CREATE VIEW
  scroll_<name> AS <query>`. Casting a Scroll is `SELECT * FROM scroll_<name>`, through the pipeline.
- Scrolls persist in the save (prompt 05 adds the save file; until then, in memory).
- Scroll names follow the same rules as player names (prompt 06); they can be renamed and deleted.
  Parameters (`{foe}`) are a later step: leave a TODO and a test marked skip.

## Tests I expect

- Old lock tests removed; new tests: every allowed statement runs; every still-forbidden one is
  refused with its line; multi-statement text is refused unless it is one transaction block.
- Snapshot/rewind round-trips schema and data; rewinding costs the turn and is logged.
- Each `damaged`/`broken` class produces its reaction exactly once per cooldown; the Grimoire
  refuses to delete the witch.
- Every brain in the roster returns a legal or confused intent for every damaged-state fixture
  (dropped `spells`, dropped `foe_spells`, deleted foe row, renamed `power` column, empty `spells`).
- Technique first-use unlocks exactly one Codex page; using a technique never miscasts for being
  "locked".
- Typing during the foe's turn changes nothing; the first frame after `--start knight` is closed
  when the Knight opens.
- A Scroll cast goes through `guard.inspect` and `cast.resolve`; the view exists in the database.
