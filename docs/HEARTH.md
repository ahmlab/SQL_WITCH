# The Hearth

The camp between regions (prompt 08 §2, pillar 5). After every guardian the party rests here;
a protagonist who faints at the end of a fight (Fatigue's top band) wakes here. Code:
`magic/hearth.py` (rules, no pygame) and `engine/hearth.py` (the screen). Data: `data/hearth/`.

## What can be done

| Action | What it does | Where to change it |
|---|---|---|
| Sleep | Fatigue back to 0 (`fall.sleep`); resets the count of nights without sleep | `data/fatigue.json` |
| Cook | A query over `recipes` (and `pantry`): the first recipe in the result is supper, if the pantry has its `needs`; Fatigue falls by the recipe's `rest`; one supper a night | `data/hearth/recipes.csv`, `pantry.csv` |
| Talk | A companion's talk node; its `<<if>>` lines choose what is said | `data/story/hearth.script` |
| Letter box | One letter per region, arriving when its guardian is beaten; reading one rests a little (`fall.letter`) and gives a Focus charge | `data/hearth/hearth.json` (`letters`), `data/story/letters.script` |
| The stall | Buying is `INSERT INTO items ... SELECT ... FROM stall` (docs/EXPLORATION.md) | `data/hearth/stall.csv` |
| The mirror | The character creator, without the name | — |
| Scroll shelf | The saved Scrolls (views): read them, throw one away | — |
| World backup | A named SQL dump of the world (the witch, the satchel, the Scrolls), kept in the save; the Chronomancer's fight restores one. The shelf keeps `backups` of them | `data/hearth/hearth.json` |
| Leave | Allowed without sleep: Fatigue rises by `rise.skipped_sleep`, the companions notice (`leave` node), and after `burnout.skips` nights in a row the companion named in `burnout` burns out (the `burnout` variable) until a real night's sleep | `data/hearth/hearth.json` |

## Companions

`companions` in `data/hearth/hearth.json`: an id, a name, the guardian after which they join
(`joins_after`), and their `talk` and `leave` nodes. A talk node reads these variables: `fatigue`
(0-1), `band` (rested, tired, exhausted, spent), `slept`, `ate`, `skipped_sleeps`, `burnout`,
`visits`, `beaten.<guardian>`, `letters` (how many have been read), `story` (every story variable).

## Writing

The Hearth's lines are `data/story/hearth.script`; letters are `data/story/letters.script` (one
node per letter, one line per paragraph; Sam writes in second person). Both follow
docs/WRITING.md and are translated like every script (docs/LOCALISATION.md).
