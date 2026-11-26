# 01 — Themes: what the game says and how it says it

Rules for the writing voice, for every line in the game:

- **Funny before wise.** A joke first; the point arrives on the way out.
- **Show before tell.** A mechanic says it before a character does; a character never explains
  the theme.
- **No speech longer than four boxes.** If it needs five, it needs a scene.
- **The Grimoire teases, the guardians taunt with truth, companions talk about dinner.**

---

## Theme 1 — Rows are people

**The claim.** Data work is not busywork: behind every row is someone whose life changes when
the query is right. The protagonist arrives believing "nobody reads these dashboards"; the game
answers by letting her read rows that are people, and by showing what changes when she does.

**Mechanics that embody it.**
- Every table in a region is a population: villagers, refugees, books, soldiers. The protagonist's
  own `witch` row sits among them (she is a row too).
- Region problems are solved by a query; the region visibly changes afterwards (fields replanted,
  gates opened, names restored). The change is driven by the result rows, not by a cutscene flag.
- `DELETE` without `WHERE` on a table of people triggers a reaction the game takes seriously
  (prompt 02): the world grieves, and only a backup brings them back.

**Scenes that dramatise it.** The harvest village reads its ledger and finds the family that was
left out (region 1); the Filter Keep lets in refugees it was turning away by mistake (region 2);
the Gravedigger's graves are rows of names the town forgot (Act 2).

**Real-world counterparts, per region** (named in each Codex page, see 02_world.md): harvest
yield reports, refugee and asylum intake screening, library catalogue cleanup, master-data
matching between two hospital systems, casualty counting and reconciliation, nested eligibility
rules in welfare benefits.

**What the player does that proves it.** Chooses to read before acting (free looks rise across
the game), and in region quests picks the query that finds the person rather than the one that
merely wins the fight. Measured: tables consulted per battle and villager quests completed.

## Theme 2 — The cost of a life eaten by work

**The claim.** The protagonist died at a desk. The game never says "work less". It shows the
cost: tiredness narrows what you can see, the people waiting for you write letters, and the one
who never stops breaks first.

**Mechanics that embody it.**
- **Fatigue** (prompt 08): it rises per battle round, per cast and per region; it shrinks the
  page (4 → 3 → 2 rows), blurs the result, and at the top band the protagonist faints after the
  battle and wakes at the Hearth. Rest is the only full cure.
- **Letters** from home arrive only at the Hearth: a player who never rests never reads them.
- **A companion who never rests** (see 03_cast.md) burns out if the party skips the Hearth twice
  in a row; they return only after a proper rest scene.
- The Statistics screen shows the player their own Fatigue history and session lengths, without
  comment.

**Scenes that dramatise it.** The office opening (the 99% bar, the flatline); the first letter
at the Hearth; the companion's burnout scene in Act 2; the finale's last letter.

**What the player does that proves it.** Rests before Fatigue forces them to, reads the letters,
and in Act 2 takes the companion home before the burnout. Measured: Hearth visits per region,
letters read, the burnout scene avoided.

## Theme 3 — Build, with the machine

**The claim.** A machine will write SQL faster than any person. Understanding is what lets the
protagonist direct it, and a directed machine builds more than either alone. The finale is
directed, not typed.

**Mechanics that embody it.**
- **The Automaton** (Act 3, 05_automaton_and_null.md) drafts queries instantly from a request; its
  drafts **drift** (one semantic slip with perfect syntax). Cast unread, they fail; read and
  corrected, they win. Its drift rate falls as the player corrects it: the machine learns from a
  person who understands.
- Scrolls (saved views) are the player's own tools; in Act 3 the Automaton can build on them.
- The final battle's victory condition is reading: spotting the drift, choosing the right shape
  for the request, never typing speed.

**Scenes that dramatise it.** The Automaton's first offer ("I can write that for you"); the trial
where its unread drafts nearly kill the party; the reconciliation; the finale against NULL.

**What the player does that proves it.** Edits drafts before casting (corrections per draft rise,
blind casts fall), and asks for shapes that use what they learned (a filter on weakness, a join on
the right key).

## Theme 4 — Learning has intrinsic value

**The claim.** What you learn is yours, written in your own hand, and worth having even when a
machine knows it too.

**Mechanics that embody it.**
- The **Codex** records every technique in the player's own first query, not a textbook example;
  a guardian's demonstration is recorded under the guardian's name, the player's first use under
  theirs.
- Nothing is locked: any SQL works from the start (prompt 02). The Codex celebrates knowing, it
  does not gate it. The Trickster pages reward knowledge used cleverly.
- The Statistics screen: "you started using WHERE in the Filter Keep and have used it 41 times
  since".

**Scenes that dramatise it.** The Grimoire rereading the player's first query aloud at the end of
Act 1; NULL attacking the Codex in the finale ("the machine knows all of this"), and the Codex
answering with the player's own queries.

**What the player does that proves it.** Opens the Codex unprompted; uses Act 1 techniques in
Act 2–3 fights where they are optional (the concept map measures recurrence).

## Theme 5 — Rest, family, time

**The claim.** Rest is not a reward for work; it is where the reasons for working live.

**Mechanics that embody it.** The Hearth loop between regions: sleep, cook (a query over the
pantry), talk to companions, read letters, look in the mirror, manage Scrolls, save a world
backup. Leaving without sleeping is allowed; the companions notice.

**Scenes that dramatise it.** Each region ends at the Hearth; the companions talk about dinner,
family, the road; the final letter; the ending's choice between return and stay.

**What the player does that proves it.** Treats the Hearth as a place, not a menu: time spent
there, conversations had, meals cooked. Measured: Hearth time against road time (Statistics).

---

## Questions for the team

1. Is "rows are people" ever too heavy for "funny before wise"? Which region problem should stay
   light (the library?) and which can carry weight (the barracks counting its dead)?
2. Fatigue fainting after a battle: punishment or care? Should the first faint be scripted, so the
   player learns it safely?
3. Should the protagonist ever *say* the thesis, even once, at the end, or must it stay unsaid?
4. How much does the Statistics screen editorialise? (Today: none; the Grimoire winks only at
   never-opened tables.)
5. Do we credit real analysts for the real-world counterparts (interviews, a short note in the
   Codex)?

Sign-off: ____________________ ____________________ ____________________
