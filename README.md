# SQL Witch

A turn-based pixel-art RPG where your queries are spells.

Ada, a data analyst convinced that SQL is busywork, dies at her desk and wakes up in the
Kingdom of Codd, a world that is literally a relational database. Magic is querying: every
attack is a real SQLite query run against the living tables of the world, and the enemies
answer with their own real SQL.

This build is the **vertical slice**: title screen, the intro story, a battle against the
**Asterisk Slime** (who teaches `LIMIT`), then the Filter Keep and a battle against
**Sir Wherewell, Knight of the Filter** (who teaches `WHERE`), with win/lose screens.

Both guardians are rule-based AIs (no machine learning): perception, a state machine written
with `match`/`case`, goal-driven behaviour and steering behaviours. See
[`docs/AI.md`](docs/AI.md) for how each requirement maps to the code.

## The rules in one minute

- Write a `SELECT`. Every result row that contains the name of a spell Ada knows **casts it**.
  A combatant's name in the same row picks the target.
- **The Rule of the Page:** the Grimoire's page shows only **4 rows** and about 36 characters.
  You pay MP for every spell your query summons, but only the rows you can read take effect.
  `SELECT * FROM spells` casts four spells and burns the rest of your mana in the margin.
- A query that returns no spell names is a **free look** (3 per turn): scry before you cast.
- Power, cost and element always come from the tables. `SELECT name, 9999 AS power` changes nothing.
- Ada starts knowing only `SELECT` and `FROM`. Each guardian casts first, so its query is
  the first thing you read. When its book shows its signature keyword, the rune glows and Ada
  copies it; she keeps it after the victory.
- Sir Wherewell's Ward of Relevance turns aside every spell that is not super-effective
  against him. Scry him (`SELECT * FROM enemies`), then filter for his weakness.

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
| `--start knight` | Start the story at the second guardian (with `LIMIT` already learned). |

| Key | Action |
|---|---|
| `Enter` | Title and dialogue: continue. In the editor: new line. |
| `Ctrl+Enter` | Cast the query (also fast-forwards the battle narration). |
| `Tab` or `→` | Accept the shaded suggestion after the cursor: the rest of a word (`SE` → `SELECT`) or the next piece of the query (`SELECT` → `name` → `FROM spells`). |
| `Up` / `Down` | Previous / next query in the history (from the first / last line). |
| `Ctrl+L` | Clear the query. |
| Hold `Backspace` / arrows | Keep deleting / moving. `Ctrl+Backspace` deletes a word, `Ctrl+←/→` jump a word. |
| `Shift+←/→` or mouse wheel | Scroll the result page sideways to read columns past the edge (looking only). |
| `F4` or click **TABLES** | Every table and its columns; click a name to write it in the query. |
| `F3` or click **? GUIDE** | The spell guide: how to write a query, how to read a table, ready-made queries to try (Enter writes one on the page) and the runes. |
| `F1` | Debug overlay: what the Slime's brain decided and why. |
| `F2` | Mute / unmute sound and music. |
| `Esc` | Skip the intro; quit from the title or result screen. |

In the terminal, no pygame needed. It plays the same battle with the same rules:

```bash
python -m sim.play_cli --seed 7
```

Add `--foe knight` to fight Sir Wherewell instead.

Type a query and press Enter. `:help`, `:why` (the Slime's reasoning), `:schema`, `:quit`.

## New to SQL?

Press **F3** in battle (or click **? GUIDE**, top right). The guide explains what a query
is, what each table holds, how to read a result, and lists queries you can try right now,
each marked as a free LOOK or a CAST. Its text lives in `data/guide.json`.

## Sound and music

All sounds live in [`assets/audio/`](assets/audio/), and
[`assets/audio/sounds.json`](assets/audio/sounds.json) says which file plays for each event
(damage, HP/MP bars going down or up, casting, fizzling, the battle music...). Swap in your own
files by editing that JSON; see [`assets/audio/README.md`](assets/audio/README.md). The
current sounds are placeholder chiptunes made by `python -m tools.make_sounds`.

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
| `ai/perception.py` | What a guardian senses each turn, and its memory of Ada's casts. |
| `ai/goals.py` | Goal-driven behaviour: atomic and composite goals, the Think arbitrator. |
| `ai/steering.py` | Steering behaviours: seek, flee, arrive, pursue, evade, wander. |
| `ai/guardian.py` | The turn loop every guardian shares: perceive, mode, think, act, move. |
| `ai/fsm.py` | The Asterisk Slime: a probabilistic state machine driving simple goals. |
| `ai/knight.py` | Sir Wherewell: stance machine and six goal plans. |
| `ai/styles.py` | Turns an intent into SQL: the Slime's `SELECT *`, the Knight's precise `WHERE`. |
| `ai/roster.py` | The guardians in order, with their level, runes, brain and style. |
| `engine/` | Everything that touches pygame: rendering, editor, Grimoire, scenes, audio. |
| `assets/audio/` | Sound effects, battle music and `sounds.json`. |
| `tools/make_sounds.py` | Generates the placeholder chiptune sounds. |
| `sim/play_cli.py` | The terminal battle. |
| `data/` | CSV game data and dialogue (see `data/README.md`). |
| `tests/` | pytest suite. |

A foe's brain only chooses an *intent*. The style layer writes it as SQL, the intent is thrown
away, and the query goes through exactly the same pipeline as the player's. Damage can only
come from the rows the query really returns.
