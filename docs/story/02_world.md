# 02 — The Kingdom of Codd

Everything in Codd is a row. The sky is a table (its columns are the stars); rivers are streams of
inserts; old ruins are dropped tables whose names are still carved on the stones. Magic is
querying, and a Grimoire is how a person reads the world.

**The map.** Act 1 is a line (seven regions, one after another). Act 2 branches: from the
Crossroads Hearth the party picks two regions in any order, then the other two, then the
Chronomancer's Clocktower, which needs all four. Act 3 converges on the Foundry and the Null Sea.

Each region: its **problem** (a real analyst problem in costume), its **people** (three named
NPCs with jobs and families), its **guardian** and why it guards, the **SQL concept**, what
**changes** when it is solved, **palette and time of day**, **music mood**.

---

## Act 1 — Reading the world

### 1. The Glade of First Rows (tutorial) — SELECT/FROM
- **Problem.** None yet: a practice field. The Training Dummy stands where travellers learn to read.
- **People.** *Old Meg*, scarecrow-maker, makes dummies for the whole kingdom; her grandson *Pip*
  wants to be a witch; *Hob*, the glade's goat, eats unread scrolls.
- **Guardian.** The Training Dummy (scripted): "I guard nothing. I am straw."
- **Changes.** The Dummy's challenge board appears; Pip follows the party to the first village.
- **Palette / time.** Greens and cream, early morning. **Music.** Light pizzicato, the tutorial loop.
- **Counterpart.** Opening a database for the first time; `SELECT *` to see what is there.

### 2. Asteria, the Harvest Village — LIMIT
- **Problem.** The harvest ledger is enormous; everyone reads all of it every morning and no one
  finishes. The Asterisk Slime grew fat on unread rows.
- **People.** *Wenna Barley*, farmer, three children, her field missing from the ledger's top rows;
  *Tobias Quill*, the village clerk who prints everything; *Nell*, the baker, who wants only today's
  orders.
- **Guardian.** The Asterisk Slime (probabilistic FSM): it guards the ledger by being the whole
  ledger. It eats whatever it is asked for, all of it.
- **Concept.** LIMIT: ask for the first few rows; pay for what you read.
- **Changes.** The clerk prints a one-page morning report; Wenna's field is finally read and
  replanted.
- **Palette / time.** Gold and green, midday. **Music.** A jig (the Glade jig theme).
- **Counterpart.** Paging a huge report; top-N dashboards; "LIMIT 10 before you scroll a million rows".

### 3. The Filter Keep — WHERE
- **Problem.** The Keep admits travellers by reading every row of every traveller, then guesses.
  Refugees wait outside for days; spies walk in.
- **People.** *Captain Ilse Marsh*, gate captain, sleeps at her post; *Ravi*, a refugee carpenter
  with his daughter *Asha*; *Brother Fen*, the monk who keeps the arrival rolls.
- **Guardian.** Sir Wherewell, Knight of the Filter (decision tree): his Ward of Relevance lets
  through only what matters. He guards the gate because he believes nothing else will.
- **Concept.** WHERE: keep the rows that pass a test.
- **Changes.** The gate admits by criteria; Ravi and Asha get in; Captain Ilse goes home to sleep
  (first Fatigue joke).
- **Palette / time.** Slate and wine, afternoon. **Music.** The Filter Keep march.
- **Counterpart.** Eligibility screening, intake triage, fraud filters.

### 4. The Scattered Library — ORDER BY
- **Problem.** The books are shelved in the order they arrived; finding the newest law takes days.
- **People.** *Sage Orla*, head librarian, nearsighted; *Dex*, apprentice who alphabetised the
  cats; *Mrs Pell*, who needs the oldest deed to save her house.
- **Guardian.** The Sorting Sage (utility + softmax): sorts everything, by whatever pleases it most
  that day. It guards the shelves from people who will not say what order they want.
- **Concept.** ORDER BY, ASC/DESC.
- **Changes.** The library opens with a catalogue; Mrs Pell keeps her house.
- **Palette / time.** Amber and leather, evening lamplight. **Music.** A slow saltarello on harpsichord.
- **Counterpart.** Sorting reports by date or value; finding the latest record.

### 5. The Twin Archives — JOIN
- **Problem.** Two archives (births and the census) record the same people under different
  numbers; no one can be matched, so pensions go unpaid.
- **People.** *Archivist Una* (births) and *Archivist Ivo* (census), siblings not speaking; *Grandpa
  Teodor*, owed twenty years of pension.
- **Guardian.** The Twin Archivists (expectimax): two halves of one guardian that cannot act
  together unless joined on the right key.
- **Concept.** JOIN ... ON, the right key, what a missing key does.
- **Changes.** Teodor's pension is paid; the twins speak again (they share a dinner at the Hearth).
- **Palette / time.** Two halves of the screen: teal and amber, dusk. **Music.** A duet in canon.
- **Counterpart.** Master-data matching; joining two hospital systems; deduplication keys.

### 6. The Barracks of Echoes — GROUP BY / HAVING
- **Problem.** After an old war, no one knows how many soldiers came home from each company;
  families still wait at the gate.
- **People.** *Sergeant Bram*, keeps the muster rolls; *Lio*, a widow who still sets two plates;
  *Corporal Tess*, who counts everything twice.
- **Guardian.** Count Aggregor (behaviour tree): counts forever and never says the total.
- **Concept.** GROUP BY, COUNT, SUM, HAVING.
- **Changes.** A memorial with the right numbers per company; Lio learns her husband's company came
  home late, and he is on the list. (Keep it tender, not grim: he is alive.)
- **Palette / time.** Grey and red, a rainy morning. **Music.** A muffled drum, then a hymn.
- **Counterpart.** Aggregated reporting, reconciliation of totals, casualty and survivor counts.

### 7. The Crypt of the Nested Lich — subqueries
- **Problem.** The kingdom's welfare rules are nested: "help those poorer than the average of
  those helped last year". The clerks gave up; the Lich feeds on the confusion.
- **People.** *Mother Ada-Rue* (an old witch who shares the protagonist's default name: a wink),
  *Clerk Silas*, who resigned; *Kit*, a child who needs the help.
- **Guardian.** The Nested Lich (MCTS): an answer inside an answer inside an answer.
- **Concept.** Subqueries, WITH.
- **Changes.** The benefit reaches Kit's family. End of Act 1: the Grimoire rereads the player's
  first query.
- **Palette / time.** Violet and bone, night. **Music.** Dark organ with a hopeful last chord.
- **Counterpart.** Nested eligibility rules; comparisons against computed averages.

---

## Act 2 — Changing the world (branching)

From the **Crossroads Hearth**, two of the four first, in any order; then the other two; then the
Clocktower.

| Region | Concept | Guardian | Problem (counterpart) | People | Changes |
|---|---|---|---|---|---|
| **Gravesend** | INSERT | The Gravedigger | The town's records lost its people; the dead are more counted than the living (restoring deleted records; onboarding) | Undertaker *Maud*, ghost-clerk *Percy*, the orphan *Rook* | The forgotten are re-inserted; Rook finds his family's names |
| **The Scriptorium** | UPDATE | The Cursed Scribe | Stone decrees state wrong facts that hurt people (correcting master data; fixing a wrong tax rate) | Scribe-apprentice *Ines*, the falsely accused *Mr Oake*, Mayor *Brisk* | The wrong decree is corrected; Oake is freed |
| **Hoardmoor** | DELETE | The Hoarder | Rows pile up until no one can find anything; some are people's treasures (data retention, GDPR deletion) | Rag-and-bone *Jory*, the hoarder's sister *Mab*, the child *Tilly* | Clutter cleared with care; Tilly's toy kept |
| **The Drafting Halls** | views/constraints | The Architect | A city built with no rules collapses each week (schema design, constraints, views as contracts) | Builder *Sanne*, the inspector *Holt*, tenant *Old Gus* | A UNIQUE rule saves the houses; views become maps others use |
| **The Clocktower** | transactions/backups | The Chronomancer | Time is rewritten every hour; nothing stays true (transactions, backups, disaster recovery) | Clockmaker *Esme*, her apprentice *Bo* | The town's history is restored from a backup the player made at the Hearth |

Palettes: Gravesend (dusk blue, candles), Scriptorium (parchment and red ink), Hoardmoor (brown and
rust, fog), Drafting Halls (white and navy, noon), Clocktower (gold and night). Music moods: a waltz
for the dead, a scratching quill motif, a cluttered polka, a clean minuet, a ticking theme that
speeds up.

---

## Act 3 — The machine

| Region | Concept | Guardian | What happens |
|---|---|---|---|
| **The Foundry** | directing an AI | The Automaton (ally and trial) | It offers to write every spell; its drafts drift. The trial is won by catching drift. Then it joins the party. |
| **The Null Sea** | IS NULL / COALESCE + the run's habits | NULL, the Voice of Doubt | A sea of missing values. NULL speaks with the player's own statistics. The final battle: direct the Automaton against NULL. |

Palettes: the Foundry (black and molten gold, no daylight), the Null Sea (grey on grey, colour
returning as the player wins). Music: industrial ostinato with a human melody on top; near-silence
that grows into the main theme.

---

## Questions for the team

1. Act 1 has seven regions: too long before Act 2? Could ORDER BY and subqueries be minor
   regions (a single scene and an encounter), keeping five full ones?
2. Is "Mother Ada-Rue" a fun wink or confusing for a player who renamed their protagonist?
3. The Barracks: is the war theme right for the tone? An alternative: a mine counting miners.
4. Act 2 order: should the Chronomancer require all four, or only three (more freedom)?
5. Names: we used English puns (Wherewell, Aggregor). Do translators keep them or invent local
   puns? (Proper names are data in the database today: see docs/LOCALISATION.md.)

Sign-off: ____________________ ____________________ ____________________
