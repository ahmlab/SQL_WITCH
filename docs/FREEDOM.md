# Freedom, consequences and Rewind

Since sandbox v2 (plan §4.1, decision D10) the player may write any SQL the world allows:
`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE TABLE / VIEW / INDEX / TRIGGER`, `ALTER`,
transactions, `UNION`, recursive `WITH`. The world reacts, and there is always a way back.

## What is still refused, and why

Only what would hurt the program, never the world (`magic/guard.py`):

| Refused | Why |
|---|---|
| `ATTACH`, `DETACH` | they reach files outside the battle's database |
| `VACUUM`, most `PRAGMA`s | they act on the database file itself; `table_info`, `table_list`, `index_list`, `index_info` and `foreign_key_list` are allowed |
| `random()`, `randomblob()`, `zeroblob()`, `load_extension()` and any function not on the list | chance comes from the battle's random generator only (same seed, same fight); blobs fill memory |
| two statements in one cast | except one `BEGIN … COMMIT` (or `ROLLBACK`) block |
| a query over 50 ms, over 10 MB of data, or too deep | the game must never freeze |
| a string in a `SELECT` list (`SELECT 'Ember'`) | the forgery ward: spell names are read from tables, not typed |

A transaction left open at the end of a cast is rolled back, and the Grimoire says so: a
snapshot cannot be taken while one is open.

## What the world does about it

After every query, `magic/world.py` compares the database with what it was and with what a fight
needs (`data/world.json`), and classifies it:

- **intact**: nothing the player did changed the world;
- **altered**: data changed (a spell inserted, an item updated);
- **damaged**: something the fight needs is gone, empty or unreadable; the fight goes on, wounded;
- **broken**: the witch's or the foe's row is gone; the engine cannot go on. Ada gets one more turn
  to rewind; otherwise the fight ends in **confusion** (no winner, no reward, the Codex page on
  backups).

Then `data/reactions.json` decides who speaks and what happens. Every entry is one rule:

```json
{"id": "drop_spells",
 "when": {"table": "spells", "change": "dropped", "actor": "player"},
 "speaker": "foe", "line_key": "reaction.drop_spells", "effect": "foe_rages", "cooldown": 99}
```

- `when.change` is one of: `dropped`, `emptied`, `created`, `rows_added`, `rows_removed`,
  `rows_changed`, `columns_changed`, `became_view`, a need's change from `world.json`
  (`foe_row_removed`, `witch_row_removed`, `unreadable`), a statement verb (`insert`, `update`,
  `delete`), or for whole casts `committed`, `transaction_left_open`, `rollback_no_transaction`,
  `commit_no_transaction`, `rewind`.
- `effect` is one of: `none`, `foe_rages` (the foe hits `rage_multiplier` times harder until the
  world is rewound), `foe_forgets` (it stares at an empty book), `fight_ends_confused`, `refuse`
  (the query is undone and refused with the line: used for the witch's own row),
  `forget_chart` (every element hits normally), `codex_unlock` (with `page`).
- `line_key` is a key in `data/i18n/en.json` (and the other languages): the text lives there.
- `cooldown` is in rounds; `99` means once per fight.

**To add a reaction:** add an entry here and its line under `reaction` in `data/i18n/en.json`.

Some protections are rules of the engine, not reactions: a spell's cost and power are never read
as negative (no MP from a spell that costs -100), a row whose numbers are not numbers is not a
spell, HP and MP are owned by the engine (`UPDATE witch SET hp = 999` is corrected after the
query), and a name used twice across the tables is refused in character.

## Tricks: breaking a guardian with knowledge

`data/tricks.json` lists the tricks the game recognises and rewards (a Codex "Trickster" page, an
achievement). Today: replacing `foe_spells` with a view the foe then reads, and reading the foe's
own query out of `query_log`. A break that is not a known trick still ends in confusion; read the
playtests' `query_log` to find new ones, then add them (each needs a small recogniser function
in `magic/world.py`).

## Rewind (F6)

Before each of the player's queries the battle database is copied (SQLite's backup API: about
0.1 ms, schema included) with the battle state. F6 lists those snapshots ("turn 3: you dropped
spells"); choosing one restores the database and the state, costs the turn, is written to
`query_log`, and the guardian comments. The 20 most recent are kept (`snapshots_kept`). The
tutorial has no Rewind: it puts the world back after every query on its own.

## The Codex (`story/codex.py`, `data/codex.json`)

Nothing is locked any more. The first time a technique is used, by the player or demonstrated by
a guardian, its page unlocks: the explanation and the SQLite / PostgreSQL / MySQL note (catalog
keys `codex.page.<id>.title`, `.text`, `.dialects`), the guardian's example and the player's own
first query. If the player already used a guardian's technique, the guardian acknowledges it
instead of teaching it. **To add a page:** add its id to `order` in `data/codex.json` and its three
lines to the catalog.

## Scrolls (F7, `magic/spellbook.py`, `data/spellbook.json`)

A query that succeeded `threshold` (3) times can be saved with F7. A Scroll is a real view,
`CREATE VIEW scroll_<name> AS <query>`, so it is cast as `SELECT * FROM scroll_<name>`, through
the normal pipeline. Scrolls belong to the player: they are recreated in every fight and after a
Rewind. Renaming and deleting exist in code; parameters (`{foe}`) are a later step.

## The turn lock

The book is closed outside the player's turn: the left page shows why ("it is Asterisk Slime's
turn"), and keys pressed then are dropped with a soft sound, never saved for later.
