# 05 — The finale: the Automaton and NULL

## The Automaton

A brass figure in the Foundry that writes SQL faster than anyone. It is not an LLM and needs no
network (prompt 09): a generator that turns a **request** into a syntactically perfect query.

### How it offers queries
- The Grimoire gains an **"ask the Automaton"** page. The player picks a **shape** (filter, sort,
  join, aggregate, write) and a **target** (a table, a column, a value) from a small structured
  menu, or gives **an example** (a Scroll: "like this, but for Tide").
- The draft appears **in the editor, for editing**. Casting it unedited is allowed. That is the
  point.

### How drift works
- With probability `drift_rate`, a draft contains exactly **one semantic slip**, never a syntax
  error and never forbidden SQL: the wrong column (`power` for `mp_cost`), the wrong table
  (`foe_spells` for `spells`), an off-by-one comparison (`>` for `>=`), a missing join condition, a
  `LIMIT` that cuts the row that mattered.
- The slip is always **readable**: a player who reads the draft against their request can see it.
  No slip depends on hidden data.
- `drift_rate` starts high in the trial (0.6), falls by a step each time the player corrects a
  draft before casting it (the Automaton learns from a person who understands), and rises a
  little when a drifted draft is cast blind. It is saved and shown ("drift: 12%").

### How the player corrects and directs
- **Correct:** edit the draft before casting. The game compares the cast query with the draft: an
  edit that fixes the slip counts as a correction.
- **Direct:** ask for a better shape ("a filter on weakness, then a limit"). Good requests produce
  drafts with fewer chances to drift (the generator has less to guess).

### How the trial punishes blind acceptance without feeling unfair
- Every drifted draft that is cast fails **visibly and explainably**: the result page shows the
  wrong rows, and the Grimoire points at the slip afterwards ("you asked for the cheapest; it
  sorted by power").
- The trial is won only by catching drift (three corrected drafts end it), never by damage. Losing
  costs nothing (D12); the Automaton's lines make the lesson funny ("I am very fast. I am
  sometimes very fast in the wrong direction.").
- Ottokar's refusal is a second path: the player can ignore the Automaton entirely and type
  everything. The trial still ends (slower, harder); the Automaton notes it with respect, and the
  reconciliation still happens.

## NULL, the Voice of Doubt

The final guardian: not a monster, a mood. "Why learn? The machine knows."

- **Its model.** The N-gram player model from the school project, now reading the **whole run's
  log** (`GameState.log`): the player's technique sequences, their habits, their most-cast query,
  their overflows, the tables they never opened.
- **Its lines are built from true numbers.** "You have written WHERE forty-one times. The machine
  does it in one." "You never opened `type_chart`. Why start now?" "Your favourite spell is
  `SELECT name FROM spells LIMIT 2`. Predictable." A test checks every number against a fixture log
  (prompt 09).
- **Its attacks** are missing values: it turns the party's columns to NULL; COALESCE and IS NULL
  are the defence; predicting the player's habits (the N-gram) lets it pre-empt the most likely
  spell.

## The final battle

- The protagonist **directs** the Automaton against NULL: NULL anticipates the player's typed
  habits, but it cannot anticipate a well-directed request.
- **Victory requires reading, not typing.** Each round NULL hides the truth in a column of NULLs;
  the Automaton drafts a query to reveal it; the draft has one slip (drift returns, raised by NULL's
  doubt); the player must read, correct and cast. Three rounds in which the corrected draft
  reveals the truth win the battle. Typing speed is never measured; a fully typed query by hand
  also works, but NULL predicts typed habits and reflects most of them.
- The last blow is the player's Codex: their own first query, cast one more time, against NULL's
  "the machine knows". NULL: "...you know it too." It fades into an empty cell.

## Two endings

- **Return.** The protagonist wakes at the desk at 11:59 pm. The report reached 100%. They close
  the laptop, call Sam, and go home. Says: understanding was the point, and rest is what it is for.
  Sam's last letter, in our world, is a text message: "You called! See you Sunday."
- **Stay.** The protagonist stays in Codd as the Hearth's witch, teaching Pip to read. Says: the
  work was worth doing where it changes lives; staying is chosen, not drifted into. Sam's last
  letter, in Codd: "I'm proud of you. Write back. Rest."
- Neither ending is "better"; both require having read the letters to land fully (a player who
  never rested gets a shorter, quieter version of each).

---

## Questions for the team

1. Should the Automaton's menu include free text ("ask in words")? It would need a parser; the
   structured menu keeps it honest.
2. Is 0.6 the right starting drift for the trial? (Simulator bands in prompt 09.)
3. NULL's lines use the player's real habits: is any of it uncomfortable (e.g. playtime, Fatigue)?
   Which statistics are off-limits?
4. The return ending at 11:59 pm: does "the report reached 100%" undercut the theme (work
   finishes anyway) or support it (it never needed you to die for it)?
5. Do companions appear in the endings? (Marta's festival, Ottokar's press, Juno's mother.)

Sign-off: ____________________ ____________________ ____________________
