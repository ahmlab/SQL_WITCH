# SQL Witch

A turn-based pixel-art RPG where your queries are spells.

Ada, a data analyst convinced that SQL is busywork, dies at her desk and wakes up in the
Kingdom of Codd, a world that is literally a relational database. Magic is querying: every
attack is a real SQLite query run against the living tables of the world, and the enemies
answer with their own real SQL.

This build is the **vertical slice**: title screen, intro dialogue, one full battle against
the **Asterisk Slime**, and a win/lose screen.

## The rules in one minute

- Write a `SELECT`. Every result row that contains the name of a spell Ada knows **casts it**.
  A combatant's name in the same row picks the target.
- **The Rule of the Page:** the Grimoire's page shows only **4 rows** and about 36 characters.
  You pay MP for every spell your query summons, but only the rows you can read take effect.
  `SELECT * FROM spells` casts four spells and burns the rest of your mana in the margin.
- A query that returns no spell names is a **free look** (3 per turn): scry before you cast.
- Power, cost and element always come from the tables. `SELECT name, 9999 AS power` changes nothing.
- Ada starts knowing only `SELECT` and `FROM`. Watch the Slime's book: when it uses `LIMIT`,
  the rune glows and Ada can copy it.

The full design is in [`docs/SQL_Witch_Design_Document.pdf`](docs/) (when present) and the
sprite brief in [`docs/SPRITES.md`](docs/SPRITES.md).

## Install

```bash
conda env create -f environment.yml
```

```bash
conda activate sql-witch
```

Python 3.12 or newer. The game itself needs only `pygame-ce` and `sqlglot`
(`pip install -r requirements.txt` works too).

## Play

In a window (keyboard only):

```bash
python main.py
```

| Option | Meaning |
|---|---|
| `--seed N` | Replay exactly the same battle. The seed is printed at start and shown on the result screen. |
| `--scale K` | Window size as a multiple of 320 × 180 (default: the largest that fits your screen). |

| Key | Action |
|---|---|
| `Enter` | Title and dialogue: continue. In the editor: new line. |
| `Ctrl+Enter` | Cast the query (also fast-forwards the battle narration). |
| `Tab` | Complete a table, column or keyword (press again for the next match). |
| `Up` / `Down` | Previous / next query in the history (from the first / last line). |
| `Ctrl+L` | Clear the query. |
| `F1` | Debug overlay: what the Slime's brain decided and why. |
| `Esc` | Skip the intro; quit from the title or result screen. |

In the terminal, no pygame needed. It plays the same battle with the same rules:

```bash
python -m sim.play_cli --seed 7
```

Type a query and press Enter. `:help`, `:why` (the Slime's reasoning), `:schema`, `:quit`.

## Tests

```bash
pytest -q
```

The suite covers the casting contract, the exploits (forged names, cross-join bombs,
duplicates, locked runes), the sandbox, the battle rules, the Slime's brain, the terminal game
and the window scenes. Engine tests run headless through SDL's dummy drivers.

## Project layout

| Path | What lives there |
|---|---|
| `main.py` | Entry point: arguments, fixed 60 Hz timestep, scene manager. |
| `magic/` | The SQL layer and the rules. **Never imports pygame.** |
| `magic/db.py` | Builds the in-memory battle database from `data/`. |
| `magic/guard.py` | Parser, rune gate, forgery ward, read-only sandbox. |
| `magic/cast.py` | Page split and the casting contract. |
| `magic/rules.py` | Damage, type chart, MP, end of round (pure Python). |
| `magic/battle.py` | Round and turn order, shared by the window and the terminal. |
| `ai/` | Foe brains and their SQL styles. **Never imports pygame.** |
| `ai/fsm.py` | The Asterisk Slime: a probabilistic finite state machine. |
| `ai/styles.py` | Turns a brain's intent into the Slime's sloppy `SELECT *`. |
| `engine/` | Everything that touches pygame: rendering, editor, Grimoire, scenes. |
| `sim/play_cli.py` | The terminal battle. |
| `data/` | CSV game data and dialogue (see `data/README.md`). |
| `tests/` | pytest suite. |

A foe's brain only chooses an *intent*. The style layer writes it as SQL, the intent is thrown
away, and the query goes through exactly the same pipeline as the player's. Damage can only
come from the rows the query really returns.
