# Items, pressure and the stall

Players could beat the school build by attacking only. These levers make the satchel, the free
look and the guardian's book matter (prompt 08 §3). Every number is in a data file.

## Items (`data/items.csv`)

An item is a row: `name, kind, amount, qty`. `qty` is the starting satchel (0: not in it). Kinds:
`hp` heals, `mp` restores MP, `ward` adds a ward, `cleanse` strips a foe's Aegis and ward (thrown
at the foe by default; with the witch's own name in the row it clears her exhaustion), `scry`
gives `amount` extra free looks on her next turn, `snapshot` makes the next Rewind cost no turn.
To add an item, add a row (its name must not be the name of a spell, a foe or the witch) and, to
sell it, a row in `data/hearth/stall.csv`. The save keeps the satchel after every victory; a lost
fight changes nothing.

## Drops and coins (`data/exploration.json`)

`drops` lists what each guardian leaves when beaten; `coins` is the starting purse and each
guardian's purse.

## Insight

`insight`: the first free look at each listed table in a battle restores `mp` MP; the first
Insight of the run opens the Codex page named by `codex` ("Looking first").
`satchel_pulse_hp`: below this share of HP (or while the foe's Aegis stands) the TABLES button,
where the satchel is, pulses when an item would help.

## Pressure (`data/pressure.json`)

A pressure move sits on top of a guardian's brain (`ai/pressure.py`) and is always a real query
on the guardian's own book.

- `big_turn` (the Asterisk Slime): when its HP share drops below `trigger_hp` (never before round
  `not_before_turn`), it spends a turn reading its big spell's power (`telegraph_sql`: the player
  sees "power 40" in its book), then casts it (`strike_sql`). A ward or a heal survives it.
  `repeat_every` rounds later it may do it again.
- `aegis` (Sir Wherewell): below `trigger_hp` he casts his `aegis` spell (Oath of Stone; its
  power is how many rounds it lasts). Every spell bounces off; items still work, and Rust Salts
  strip it. While it stands, and afterwards when `press_after` is true, he casts `during_sql`
  whenever he has `during_mp` MP. It fades on its own, so no fight is ever locked.

The guardians' and Ada's lines about these moves are in `data/story/hints.script` (topics
`telegraph` and `aegis` in `data/hints.json`).

## The stall (`magic/shop.py`)

At the Hearth the shopkeeper drafts `INSERT INTO items (name, kind, amount, qty) SELECT name,
kind, amount, 1 FROM stall WHERE name = '...'` with the player. Any read is a free look; an
INSERT into `items` is checked row by row (on the stall, same kind and amount, a unique name,
enough coins) and only then changes the save. Prices are in `data/hearth/stall.csv`.

## Balance (`sim/bots.py`)

Four simulated players write real SQL: `novice` (never limits), `attack_only` (precise, never
heals or uses items), `competent` (also wards a telegraphed turn, throws salts at an Aegis,
heals low), `expert`. The target (tests/test_pressure_and_items.py): each Act 1 guardian wins
60-75% of first attempts against `competent`, and beats `attack_only` more than 60% of the
time. To check after a change: `python -c "from sim.bots import win_rate; print(win_rate('knight',
'competent'))"`. The guardians' HP in `data/foes.csv` is the main knob (the Slime 360, the Knight
590 at the time of writing).
