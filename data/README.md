# data/

Content loaded into the in-memory SQLite database at the start of every battle (magic/db.py).
CSV and JSON cannot hold comments, so the format of each file is documented here.
Schema reference: design document, Appendix A. Starting values: Appendix B.

- `spells.csv` - Ada's spells: `name,element,power,mp_cost,kind` (kind: attack | heal | ward | area).
  Names must be unique across spells AND items (checked at load time, NOT by a database index).
- `foes.csv` - guardians and minions: `id,name,hp,max_hp,mp,max_mp,element,weakness,speed,squad`.
  NULL's hp, element and weakness are left empty so they load as SQL NULL.
  Row 3, the Training Dummy, is the tutorial's partner: speed 0 (Ada always acts first) and no
  rows in `foe_spells.csv`, so nothing it writes can ever cast a spell.
- `foe_spells.csv` - `foe_id,name,element,power,mp_cost,kind`. Besides attack/heal/ward/area,
  foes may use `relevance` (raise the Ward of Relevance: only super-effective spells land, and
  the first one shatters it) and `dispel` (remove the target's ward). Only the foes of the
  current battle (and their spells) are loaded: `build_db(level, foe_ids=[...])`.
- `items.csv` - `name,kind,amount,qty`.
- `type_chart.csv` - `attack,defend,multiplier`. Cycle: Fire > Nature > Storm > Tide > Fire;
  Arcane is neutral except x2 against Void; every other element is x0.5 against Void.
- `dialogue.json` - story beats and guardian lines, keyed by scene id. Each `intro` line has a
  `speaker` and `text`, plus: `scene` (`office`, `void` or `glade`: changing it dips to black),
  `sleep` (office only, 0 awake to 3 asleep on the desk), `book` (the Grimoire floats on screen),
  `slime` (the Slime appears), `sound` (an event from `assets/audio/sounds.json`) and
  `only_before` (`tutorial` or `slime`: said only when the intro leads there; the rules the
  tutorial teaches by doing are only spoken to players who skip it with `--start slime`).
- `tutorial.json` - the tutorial's whole script: lessons, every line, ghost levels, pass
  conditions and the hint thresholds. Its own `_help` key explains the format; the game refuses
  to start (and says which line) if a line is too long for its box. See `docs/TUTORIAL.md`.

Balance these numbers in a spreadsheet and export to CSV; never edit values inside the code.
