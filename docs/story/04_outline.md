# 04 — Outline, scene by scene

Each scene: **id** (it becomes the script node: `data/story/<region>.script`, `== id ==`),
location, who is there, purpose (what the player learns or feels), beats, choices and their
consequences, music cue, and the mechanic it introduces or pays off. Act 1 in full; Acts 2–3 by
beats. Existing nodes (already in `data/story/intro.script` and `tutorial.script`) are marked
*(exists)*.

---

## Act 1 — Reading the world

### Prologue and the Glade

**`intro`** *(exists)* — the office, then the void, then the glade. Protagonist, Grimoire.
Purpose: the death at the desk, played as a joke that lands. Beats: 11:58 pm; "nobody reads
these dashboards"; the bar stops at 99%, so does the heart; the void; grass; the sky is a table;
the Grimoire. Music: office hum → flatline → silence → glade. Mechanic: dialogue, the Grimoire.

**`tutorial_*`** *(exists)* — the Training Dummy. Purpose: reading before casting; the Rule of the
Page. Beats: LOOK, CHOOSE, READ, CAST, PLAY. Mechanic: free looks, overflow, the Codex.

**`glade_pip`** — the Glade's edge. Pip (Meg's grandson), Grimoire. Purpose: the first person who
needs the protagonist. Beats: Pip asks to see a real spell; the protagonist casts a free look at
`villagers`; Pip finds his own row ("I'm in the world!"). Choice: let Pip follow (he appears at
the Hearth later) / send him home (he writes a letter of his own). Music: tutorial loop, lighter.
Mechanic: a table of people; the first Hearth hint.

### Asteria, the Harvest Village (LIMIT)

**`asteria_arrival`** — the village square, morning. Tobias the clerk, Nell, Grimoire. Purpose:
the cost of reading everything. Beats: Tobias reads the whole ledger aloud every morning; nobody
listens; Nell only wants today's orders; the ledger's top rows never reach Wenna's field. Music:
the Glade jig, slow. Mechanic: a query against `ledger` returns 300 rows; the page holds four.

**`asteria_wenna`** — Wenna's field, midday. Wenna, her children. Purpose: rows are people. Beats:
her field is row 212; nobody reads that far; her children ask why the cart never comes.
Mechanic: villager request: "find my field" (any query that brings row 212 on the page wins: a
`WHERE`, an `ORDER BY`, an `OFFSET`... freedom, but LIMIT is the cheap way once learned).

**`slime_intro`** *(exists as part of `intro`)* — the Asterisk Slime wobbles out. **Battle:
Slime.** Pays off: LIMIT (the Invitation, the Codex page).

**`slime_mercy`** *(exists in `mercy.script`)* — overkill pleading; the Grimoire's LIMIT lesson.

**`asteria_after`** — the square, evening. Tobias prints a one-page report; Wenna's cart arrives.
Purpose: what changes when the query is right. Choice: give Tobias a Scroll (your best LIMIT
query) / keep it (the Scroll shelf at the Hearth). Music: the jig, full. Mechanic: Scrolls.

**`hearth_1`** — the first Hearth (a field camp). Marta Quill joins (she was delivering
Asteria's post). Purpose: rest is a place. Beats: Marta eats while walking; the Grimoire yawns;
the first letter from Sam. Choice: sleep (Fatigue resets) / push on (Marta approves, which is the
problem). Music: hearth theme (prompt 08). Mechanic: the Hearth, letters, Fatigue.

### The Filter Keep (WHERE)

**`knight_intro`** *(exists)* — the gate, afternoon. Sir Wherewell, Grimoire.

**`keep_gate`** — outside the walls. Ravi and Asha, Captain Ilse. Purpose: a filter that fails
people. Beats: refugees wait for days; Ilse reads every row of every traveller; she has not slept.
Mechanic: `travellers` table; a villager request: "find who may enter" (WHERE).

**Battle: Sir Wherewell.** Pays off: WHERE (the Ward of Relevance).

**`keep_after`** — inside the Keep. Ravi and Asha enter; Ilse sleeps at last (a snore in the
dialogue). Brother Fen gives the party his arrival rolls. Choice: show Fen how to filter his rolls
(+1 villager quest done) / not now. Music: the march, warm. Mechanic: query golf introduced (Fen
challenges: same result, fewer rows).

**`hearth_2`** — Hearth. Marta, Grimoire; letter 2 (the mug on the desk). If the player skipped
`hearth_1`'s sleep: Marta's first stumble (foreshadowing).

### The Scattered Library (ORDER BY)

**`library_doors`** — evening lamplight. Sage Orla, Dex, Mrs Pell. Purpose: order is a question
you must ask. Beats: books in arrival order; Mrs Pell needs the oldest deed before morning.
Mechanic: scrying puzzle (which shelf holds the oldest deed: `ORDER BY year LIMIT 1`).

**`library_cats`** — comic relief: Dex alphabetised the cats; the cats object. Minor encounter:
a "moth that hides unless you ORDER BY".

**Battle: the Sorting Sage.** Pays off: ORDER BY, ASC/DESC. Trickster goal: index the Sage.

**`library_after`** — the catalogue opens; Mrs Pell keeps her house. Letter 3 at the next Hearth
("I read the report. It was good, actually.").

### The Twin Archives (JOIN)

**`archives_split`** — dusk, a building cut in two. Una, Ivo, Grandpa Teodor. Purpose: matching is
care. Beats: two archives, two numbering schemes; Teodor unpaid for twenty years. Juno Vale is
here for a rematch with the Archivists and joins the party, loudly. Mechanic: two tables, a
cloze lock (`... JOIN census ON births.____ = census.person_id`).

**Battle: the Twin Archivists.** Pays off: JOIN ON, missing keys.

**`archives_after`** — the twins share dinner at the Hearth with the party (Juno's mother runs the
canteen: she brought soup). Choice: help Juno read her mother's clippings (+trust) / tease her.

### The Barracks of Echoes (GROUP BY / HAVING)

**`barracks_gate`** — rain. Sergeant Bram, Lio, Corporal Tess, Juno. Purpose: counting is how a
community remembers. Beats: families still wait; Lio sets two plates; Juno quiet for once.
Mechanic: a riddle gate ("How many came home in the Third Company?": `COUNT` with `GROUP BY`).

**Battle: Count Aggregor.** Pays off: GROUP BY, HAVING.

**`barracks_after`** — the memorial with the right numbers. Lio's husband's company came home late;
he is on the list. Juno finds her father's name (see 03_cast.md question 4). Music: the hymn.

### The Crypt of the Nested Lich (subqueries)

**`crypt_steps`** — night. Mother Ada-Rue, Clerk Silas, Kit. Purpose: rules inside rules. Beats:
"help those poorer than the average of those helped last year"; Silas resigned; Kit waits.
Mechanic: scrying puzzle with a subquery (a value inside a value).

**Battle: the Nested Lich.** Pays off: subqueries, WITH.

**`act1_end`** — the Crypt's top, dawn. The Grimoire rereads the protagonist's first query from the
Codex (their own, from the tutorial) and then their best one. Purpose: learning is theirs. Beats:
"You wrote this. Nobody else did." The party at the Hearth; Sam's letter 4. Music: main theme.

---

## Act 2 — Changing the world (beats)

- **`crossroads`** — the Crossroads Hearth. The Grimoire: reading is not enough; the world can be
  written. The player picks two of four regions.
- **Gravesend (INSERT).** The town's records lost its people. Beats: Maud the undertaker; Percy the
  ghost-clerk; Rook looks for his family. Battle: the Gravedigger raises minions from `graves`;
  the player inserts allies from `villagers` (`INSERT … SELECT`). After: Rook's family's names are
  re-inserted. Trickster: a trigger that traps the Gravedigger.
- **The Scriptorium (UPDATE).** Wrong decrees in stone. Beats: Ines (Ottokar's sister); Mr Oake
  falsely accused; Brother Ottokar joins. Battle: the Cursed Scribe; read first, then UPDATE; it
  rewrites them back. After: Oake freed.
- **Hoardmoor (DELETE).** Clutter that absorbs spells; some rows are treasures. Beats: Jory, Mab,
  Tilly's toy. Battle: the Hoarder; precise WHERE; a DELETE without WHERE is a tragedy with a
  reaction (and a Rewind).
- **The Drafting Halls (views/constraints).** A city without rules. Beats: Sanne, Holt, Old Gus.
  Battle: the Architect; a better view and a UNIQUE constraint the foe trips on.
- **Marta's burnout** — triggered if the party skips the Hearth twice; otherwise Marta goes home
  for the festival and returns rested (`marta_festival`).
- **The Clocktower (transactions/backups).** Esme and Bo; time rewritten hourly. Battle: the
  Chronomancer; SAVEPOINT/ROLLBACK and the Hearth backup; victory by restoring a state the foe
  never saw. Sam's letter 5 ("a backup of your voicemails") arrives just before.

## Act 3 — The machine (beats)

- **`foundry_arrival`** — the Automaton offers to write every spell, instantly. Ottokar refuses.
- **The trial** — the Automaton's unread drafts drift; the party nearly falls; the trial is won by
  catching drift. Reconciliation: it learns from corrections; it joins as an ally.
- **`null_sea`** — NULL speaks with the player's own statistics. Letter 6 ("I went to the sea").
- **The final battle** — the protagonist directs the Automaton against NULL (05_automaton_and_null.md).
- **Endings** — return or stay; the last letter answers.

---

## Questions for the team

1. Is every Act 1 region a full arrival → battle → after → Hearth? It is long; which "after"
   scenes can fold into the Hearth?
2. Wenna's field accepts any query that brings row 212 onto the page: is that freedom confusing
   before LIMIT is learned?
3. Should Pip's choice (follow / go home) matter later?
4. Juno joins at the Archives (region 5): too late for the third companion?
5. Act 2: do the companions comment on the order chosen?

Sign-off: ____________________ ____________________ ____________________
