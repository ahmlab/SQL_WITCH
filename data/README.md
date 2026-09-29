# data/

Content loaded into the in-memory SQLite database at the start of every battle (magic/db.py).
CSV and JSON cannot hold comments, so the format of each file is documented here.
Schema reference: design document, Appendix A. Starting values: Appendix B.

- `spells.csv` - Ada's spells: `name,element,power,mp_cost,kind` (kind: attack | heal | ward | area).
  Names must be unique across spells AND items (checked at load time, NOT by a database index).
- `foes.csv` - guardians and minions: `id,name,hp,max_hp,mp,max_mp,element,weakness,speed,squad`.
  NULL's hp, element and weakness are left empty so they load as SQL NULL.
- `foe_spells.csv` - `foe_id,name,element,power,mp_cost,kind`.
- `items.csv` - `name,kind,amount,qty`.
- `type_chart.csv` - `attack,defend,multiplier`. Cycle: Fire > Nature > Storm > Tide > Fire;
  Arcane is neutral except x2 against Void; every other element is x0.5 against Void.
- `dialogue.json` - story beats and guardian lines, keyed by scene id.

Balance these numbers in a spreadsheet and export to CSV; never edit values inside the code.
