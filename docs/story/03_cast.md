# 03 — Cast: the protagonist, the companions, the family

## The protagonist

**The fixed situation (D2).** An analyst in our world, good at the job and tired of it, who
thinks SQL is busywork. At 11:58 pm, waiting for a quarterly report nobody will read, they close
their eyes "until it reaches 100%". The bar stops at 99%. So does their heart. They wake in Codd
with their own name in a row of the `witch` table.

**What the player defines (D2/D3).** Name (any script, 1–12 characters), look (hair, colours,
hat, accessory) and the words the world uses for them: feminine or masculine. Ada is the default.

**How to write lines about the protagonist without assuming gender (D3).**
- In English, prefer "you" and "witch" (used for everyone in Codd). When a pronoun is unavoidable,
  write `{player.gender, select, masculine {he} other {she}}`; the i18n lint points at lines with
  he/she/his/her and no select.
- The name stands alone or in a fixed frame ("{player.name}:", "the heart of {player.name}"),
  never where a language would decline it.
- No line depends on the protagonist's body, age or background. Their history is the job, the
  desk, the report: the situation, not the person.
- Translators add selects where their language inflects (Spanish "bruja/brujo"); see
  docs/LOCALISATION.md.

**Their arc.** From "nobody reads these dashboards" to understanding what reading is for (Act 1),
what changing a record does to a person (Act 2), and what their understanding is worth when a
machine can type faster (Act 3). The ending asks them to choose where to rest.

## The companions

Three companions, one per team member if the authors like (each author writes one voice). In
battle they speak from the sidelines through the Hint Director (prompt 03), one line at most,
never the answer.

### Marta Quill — the one who never rests
- **Job.** Courier for the Kingdom's post; knows every road.
- **Family.** A husband and two small children in Asteria she sends money to and rarely sees.
- **Why on the road.** The post is late; she carries the letters nobody else will.
- **Flaw (theme: a life eaten by work).** She skips the Hearth to "just finish the route". If the
  party leaves the Hearth twice in a row without sleeping, she collapses after a battle (the
  burnout scene) and stays at the Hearth until the party rests there properly.
- **Arc and resolution.** In Act 2 she gives her route to a younger courier and goes home for a
  festival; she rejoins rested, and in the finale she is the one who tells the protagonist to stop.
- **Teaches.** LIMIT and pagination in practice ("I only carry what fits in the bag"), Fatigue.
- **Voice.** Quick, warm, always eating on the move. Talks about dinner she has not had.

### Brother Ottokar — the one who distrusts the machine
- **Job.** Monk-scribe from the Scriptorium; copies by hand.
- **Family.** His sister Ines, an apprentice scribe who loves the new presses.
- **Why on the road.** To find who carved the wrong decrees (the Cursed Scribe).
- **Flaw (theme: build with the machine).** Refuses every tool he did not make; in Act 3 he will
  not let the Automaton draft anything.
- **Arc and resolution.** In the Automaton trial he is right that blind trust fails; in the
  reconciliation he learns that a corrected draft is still his work. He becomes the party's
  editor: he reads every draft first.
- **Teaches.** UPDATE (reading before correcting), reading drafts, WHERE precision.
- **Voice.** Slow, dry jokes, Latin-sounding mottos he made up.

### Juno Vale — the one who thinks reading tables is beneath her
- **Job.** Duellist and adventurer; famous, impatient.
- **Family.** A mother who runs the Twin Archives' canteen and keeps every newspaper clipping of her.
- **Why on the road.** A guardian beat her once; she wants a rematch.
- **Flaw (theme: rows are people / learning has value).** Attacks first, reads never. Her side
  quests fail until she looks at the table.
- **Arc and resolution.** At the Barracks she counts the dead of her own father's company and
  finds his name; she starts reading. In Act 3 she challenges the protagonist to query golf.
- **Teaches.** Free looks, JOIN, GROUP BY, query golf.
- **Voice.** Loud, competitive, secretly kind. Talks about her mother's cooking.

## The family: letters home

**Who writes.** One fixed relative, in second person: the protagonist's **younger sibling**,
Sam (name editable later? see questions). Sam writes from the world the protagonist left, as if
the letters can reach Codd.

**How letters arrive.** Only at the Hearth, by story progress (one per region), in the letter box.
A player who never rests never reads them; they wait.

**Their arc, in parallel.**
1. (After Asteria) Sam is cross: "You missed my birthday again. Work, I know."
2. (After the Keep) Sam found your office: "Your desk still has the mug I gave you."
3. (After the Library) "They printed the report. Nobody read it. I read it. It was good, actually."
4. (Act 2) Sam has started a job "with spreadsheets", is tired, asks how you did it.
5. (Act 2, the Clocktower) "I keep a backup of your voicemails."
6. (Act 3) Sam writes about resting: "I took a day off. I went to the sea."
7. (The finale) The last letter answers the ending choice (05_automaton_and_null.md).

Letters are short (three to six sentences), funny first, never maudlin; the sixth one should
make players stop for a moment.

---

## Questions for the team

1. Do the three companions map to the three authors? Each author owns one voice.
2. The sibling: fixed name "Sam", or chosen in the creator? (A chosen name multiplies translation
   cases; a fixed, gender-neutral name keeps it simple.)
3. Marta's burnout: is collapsing after a battle too punishing? Alternative: she stays behind
   at the Hearth with a note.
4. Juno's father in the Barracks: alive or dead? (02_world.md keeps Lio's husband alive; we should
   not do both the same way.)
5. Should companions ever disagree with the protagonist's choices in a branch (Act 2 order)?

Sign-off: ____________________ ____________________ ____________________
