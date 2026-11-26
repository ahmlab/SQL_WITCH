# Prompt 07 — Story bible, world, companions, Hearth (design documents, not code)

This prompt produces **documents for humans to edit**, in `docs/story/`. Nothing here is wired into
the game until the team has rewritten it in its own voice. Read `docs/plan/00_MASTER_PLAN.md`
§1, §5.1, §5.2, and the Decision Log (D2, D3). The themes are fixed; the words are the team's.

---

## 0. Read and report

Read the existing dialogue, tutorial script, hint pools, the Codex data and the design PDF's story
section. Report in 10 lines what the current story establishes and what must be kept for
continuity. Stop and wait.

## 1. `docs/story/01_themes.md` — what the game says and how it says it

For each theme, one page: the claim, the mechanics that embody it (not just dialogue), the scenes
that dramatise it, and what the player should *do* that proves they got it.

- **Rows are people.** Data work benefits lives. Every region's problem is a real analyst problem
  in costume (name the real-world counterpart for each).
- **The cost of a life eaten by work.** The protagonist died at a desk. The game never says
  "work less"; it shows it: Fatigue, letters, a companion who burns out if the party never rests.
- **Build, with the machine.** The Automaton writes SQL faster than anyone. Understanding is what
  lets the protagonist direct it. The finale is directed, not typed.
- **Learning has intrinsic value.** The Codex is the protagonist's own, in their own queries.
- **Rest, family, time.** The Hearth loop; the ending.

Rules for the writing voice: funny before wise; show before tell; no speech longer than four
boxes; the Grimoire teases, the guardians taunt with truth, companions talk about dinner.

## 2. `docs/story/02_world.md` — the Kingdom of Codd

Regions for all three acts (plan §5.2 has the roster): for each region its problem, its people
(three named NPCs with jobs and families), its guardian and why it guards, what SQL concept the
problem needs, what changes when it is solved, its palette and time of day, its music mood.
The map is linear in Act 1, branches in Act 2 (two regions in any order), converges in Act 3.

## 3. `docs/story/03_cast.md` — protagonist, companions, family

- Protagonist: the fixed situation (D2), what the player defines (D2/D3), and a rule for writing
  lines about them without assuming gender (D3).
- Three companions (one per team member, if you like): a job, a family, a reason to be on the
  road, a flaw tied to a theme (the one who never rests, the one who distrusts the machine, the one
  who thinks reading tables is beneath them), an arc with a resolution, and the SQL concept each
  helps teach. Companions are also the sideline voices in battle (prompt 03).
- Family: letters that arrive at the Hearth, in second person, from one fixed relative (a parent
  or sibling); their arc runs in parallel and ends in the finale.

## 4. `docs/story/04_outline.md` — scene by scene

Every scene with: id (becomes the script node), location, present characters, purpose (what the
player learns or feels), beats, choices and their consequences, music cue, and the mechanic it
introduces or pays off. Act 1 in full detail; Acts 2–3 at beat level.

## 5. `docs/story/05_automaton_and_null.md` — the finale design

- The Automaton: how it offers queries, how drift works (syntactically perfect, semantically
  wrong in one place, with a rate that falls as the player corrects it), how the player corrects
  (edit before cast) and directs (asks for a shape: "a filter on weakness", through a small
  structured menu or by example), and how the fight punishes blind acceptance without feeling
  unfair.
- NULL: the N-gram player model from the school project, now reading the whole run's log; its
  lines are built from the player's real habits ("you have written WHERE forty-one times; the
  machine does it in one").
- The final battle: the protagonist directs the Automaton against NULL. Victory condition that
  requires reading, not typing.
- Two endings (return / stay) and what each says about the themes.

## 6. Hand-off

Each document ends with a "questions for the team" list. The team answers, rewrites, and only
then are the scenes written as `.script` files (prompt 03's format), one region at a time, by the
team with the builder as an editor, before prompts 08 and 09 wire them in.

## No tests. Review gate: the three authors sign off on each document.
