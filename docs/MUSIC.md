# The music of SQL Witch

Six pieces, all synthesised by `tools/make_music.py` with the Python standard library: five
battle themes, so two fights in a row do not sound alike, and one danger theme for when Ada is
nearly dead: the same battle, suddenly faster and more aggressive. Every file is generated the same way each time (byte for byte):

```bash
python -m tools.make_music                 # write all six
python -m tools.make_music --only lantern  # write one
python -m tools.make_music --sheet         # print the score sheets below
```

## The rules every track follows

- **No C#, D#/Eb or G#/Ab.** The typing sounds play C major pentatonic on every keystroke, and
  those three pitches would clash with them. Each piece stays in one key signature, from one
  flat to one sharp, and cadences modally (bVII to i, or v to i), with no harmonic-minor leading
  tone. That restriction is also what makes it sound medieval rather than classical.
  `tests/test_music.py` checks the note data of every track.
- **Medieval idiom.** A drone on the tonic and fifth, melodies doubled in parallel fourths or
  fifths (a tritone is turned into a perfect interval), dance metres (6/8, 3/4 with hemiolas,
  a march), grace notes, call and response.
- **Form.** 60 to 80 seconds before the loop: intro (drone and rhythm), the theme, the theme with
  a second voice, a contrasting section, a thin bridge (drone and a solo), the fullest statement,
  a turnaround. Voices enter and drop out; that is where the dynamics come from. Every bridge is
  the quietest part of its piece, every last statement the loudest.
- **Mix.** Each group of instruments is set relative to the lead: plucked strings -8 dB, bass
  -9 dB, percussion -8 dB, bells -9 dB, drone -15 dB. Every instrument is first brought to the
  same loudness, so "velocity 1" means the same thing on a recorder and a shawm. Every battle
  theme is mastered to the same loudness (-18.8 dBFS RMS); the danger theme is a little louder
  (-18.1 dBFS), so the fight feels like it escalates.
- **Seamless loops.** Rendering is circular: what still rings after the last bar (a lute note,
  the echo) is added to the first bars. The jump at the seam is no bigger than the steps the
  music already makes around it.

## The instruments

| Instrument | How it is made | Used for |
|---|---|---|
| Lute, harp | Karplus-Strong: a burst of noise circulating in a tuned delay line (an all-pass filter fixes the fraction of a sample) | arpeggios, ostinatos, the plucked bass, solos in the bridges |
| Recorder | a nearly pure wavetable, slow attack, delayed vibrato, breath and a "chiff" of noise at the start | the singing lead |
| Shawm | a narrow pulse rich in middle harmonics (nasal), two voices 5 cents apart, softened by a low-pass | the bold lead, the answering voice |
| Fiddle | a band-limited sawtooth with a body resonance, vibrato, bow noise | the dancing lead of the Estampie |
| Hurdy-gurdy | many harmonics, two voices 4 cents apart, a slow swell (it trembles in the danger theme) | the drone under everything |
| Tabor, field drum, tambourine | a falling sine "thump" plus filtered noise for the skin, the snares or the jingles; rolls of four strokes | the pulse, fills at the end of every section |
| Bell | a sine with inharmonic partials (2.76, 5.4, 8.93), each fading at its own speed | the magic colour, used sparingly |
| Heartbeat | a muffled low thump, twice, racing | the opening of the danger theme |

## Where each piece plays

`assets/audio/sounds.json` decides, not the code. An entry lists several files; each battle
picks one with the game's visual random generator (never the battle's, so the same seed always
replays the same fight), and never the one that played just before.

| Entry | Plays |
|---|---|
| `dummy` (the tutorial) | Lantern over Codd, the calm one |
| `slime` | Glade Jig, Estampie of Sparks, Lantern over Codd |
| `knight` | The Filter Keep, Saltarello of the Spire, Estampie of Sparks |
| `battle` (any other fight) | all five |
| `danger` | Last Candle |
| `classic_slime`, `classic_knight` | the two original chiptunes, kept for comparison |

**The danger switch.** When Ada's HP bar (as shown, after the narration has caught up) drops
below a quarter, the battle theme fades out and pauses while Last Candle fades in (600 ms each
way). When the bar climbs back above 35%, Last Candle fades out and the battle theme resumes
where it was paused. The gap between 25% and 35% keeps it from flapping. Staying low never
restarts it; leaving the battle stops everything; the tutorial never plays it; F2 still mutes.

## Score sheets

### Glade Jig

D Dorian, 6/8, dotted quarter = 126. 66 bars, 62.9 s. File: `theme_glade_jig.wav`.

**Motif:** D5 A4 D5 E5 | F5 E5 D5 C5 (a hop down a fourth and back, then a falling answer)

| Role | Instrument |
|---|---|
| lead | recorder (A'' adds a second recorder a fourth below) |
| accompaniment | lute arpeggios; lute bass on the beats |
| bed | hurdy-gurdy drone on D and A |
| percussion | tabor, tambourine |
| colour | bell on the strong bars of the last section |

| Bars | Section | Who plays | What the listener should feel |
|---|---|---|---|
| 1-6 | intro | drone, tabor; lute arpeggios from bar 3, bass from bar 5 | a clearing wakes up: something is about to start dancing |
| 7-14 | A | recorder states the motif over lute, bass and tabor | the tune arrives: cheeky, light on its feet |
| 15-22 | A' | recorder with a new ending; tambourine joins | the same tune, a little bolder, reaching higher at the end |
| 23-30 | B | recorder high, lute bass walks, tambourine shakes | a change of light: brighter, in F major, singing more than dancing |
| 31-38 | B' | B again, climbing to C6 at the end; drone returns | lifted up: the phrase climbs and hangs on A, unresolved |
| 39-46 | bridge | drone and a lute solo (the motif slowed down); soft tabor | a breath: the dance stops and the lute remembers the tune |
| 47-54 | A'' | fullest: two recorders in fourths, lute, bass, tabor, tambourine, bells | everyone dances: the tune at its fullest |
| 55-62 | A''' | the varied answer, with fourths and bells; tabor fill | a last flourish up to C6, then home to D |
| 63-66 | turnaround | lute on C then D, drone and tabor alone | the dance winds down to the drone it started from, and begins again |

### The Filter Keep

D Aeolian, 4/4 march, quarter = 104. 30 bars, 69.2 s. File: `theme_filter_keep.wav`.

**Motif:** D5 . . A4 D5 . F5 | E5 D5 C5 A4 (a dotted call up the D minor chord, then a step down)

| Role | Instrument |
|---|---|
| lead | shawm, doubled a fifth below from A'' on |
| accompaniment | lute strumming on the beats; lute bass in halves |
| bed | hurdy-gurdy drone on D and A |
| percussion | field drum: bass drum, snare, rolls at every section end |
| colour | bell on the downbeats of the last section |

| Bars | Section | Who plays | What the listener should feel |
|---|---|---|---|
| 1-2 | intro | drone and field drum alone, a roll into the theme | the gate of a keep: armour clinks, something solemn approaches |
| 3-10 | A | shawm alone states the motif over lute, bass and drum | a proud call, plain and confident |
| 11-18 | B | shawm high in F major; lute arpeggios instead of strums | the banners lift: brighter and higher, ending on a question (A minor) |
| 19-22 | bridge | drone and a low recorder alone; a short roll at the end | the hall goes quiet before the last charge |
| 23-30 | A'' | fullest: shawm doubled in fifths, strums, bass, drone, drum, bells | the whole garrison marches: heavy, proud, unstoppable |

### Estampie of Sparks

G Mixolydian, 3/4, hemiola in bars 3-4 of every phrase, quarter = 152. 56 bars, 66.3 s. File: `theme_estampie.wav`.

**Motif:** G5 B5 D6 | C6 B5 A5 G5 (a leap up the G chord, then a dancing fall)

| Role | Instrument |
|---|---|
| lead | fiddle (A'' adds a recorder a fifth below) |
| accompaniment | harp arpeggios; lute bass on the hemiola accents |
| bed | hurdy-gurdy drone on G and D |
| percussion | tabor, tambourine on the busy sections |
| colour | bells on the high points |

| Bars | Section | Who plays | What the listener should feel |
|---|---|---|---|
| 1-4 | intro | drone and tabor; harp arpeggios from bar 3 | sparks crackle: a bright courtyard, a dance about to begin |
| 5-12 | A | fiddle states the motif over harp and tabor | a heroic leap and a whirling fall: bright and sure |
| 13-20 | A' | fiddle again; tambourine joins; bells on the peaks | the dance gathers dancers |
| 21-28 | B | fiddle lower, in C; harp thins to the beats | a turn of the dance: warmer and lower, ending open on D |
| 29-36 | bridge | drone and harp solo (the motif slowed down) | the dancers catch their breath; the harp hums the tune |
| 37-44 | A'' | fullest: fiddle with a recorder a fifth below, harp, bass, drone, tabor, tambourine, bells | everyone in the ring at once |
| 45-52 | B' | fiddle and harp, tambourine shakes | the last turn of the dance |
| 53-56 | turnaround | a cadential hemiola on fiddle, then drone and tabor | a bow to the partner, and the dance starts over |

### Lantern over Codd

E Aeolian, 4/4, half-time drum, quarter = 92. 26 bars, 67.8 s. File: `theme_lantern.wav`.

**Motif:** E5 . G5 F#5 | E5 D5 B4 (a lifted third that sinks back, like a held breath)

| Role | Instrument |
|---|---|
| lead | recorder (soft, singing; A'' adds a second one a fourth below) |
| accompaniment | harp ostinato in eighths |
| bed | hurdy-gurdy drone on E and B |
| percussion | tabor in half time (dum on 1, rim on 3) |
| colour | bells, sparse, in the bridge and the last section |

| Bars | Section | Who plays | What the listener should feel |
|---|---|---|---|
| 1-2 | intro | harp ostinato and drone | a lantern is lit in the dark: calm, steady, a little sad |
| 3-10 | A | recorder sings the motif; harp; half-time tabor from bar 3 | a quiet resolve: this is worth fighting for |
| 11-14 | B | recorder higher in G major; bells on the downbeats | a glimpse of hope, warmer, ending open on D |
| 15-18 | bridge | harp and drone alone, a few bells | stillness: the lantern flickers, then holds |
| 19-26 | A'' | fullest: two recorders in fourths, harp, drone, tabor, bells | the same resolve, steadier now, and home to E |

### Saltarello of the Spire

A Dorian, 6/8, dotted quarter = 150. 78 bars, 62.4 s. File: `theme_saltarello.wav`.

**Motif:** A5 B5 C6 B5 | A5 G5 E5 (the recorder asks), E5 F#5 G5 F#5 | E5 D5 A4 (the shawm answers)

| Role | Instrument |
|---|---|
| lead | recorder calls, shawm answers; together in fourths at the end |
| accompaniment | harp arpeggios; lute bass |
| bed | hurdy-gurdy drone on A and E |
| percussion | tabor, tambourine, all of it |
| colour | bells on the peaks |

| Bars | Section | Who plays | What the listener should feel |
|---|---|---|---|
| 1-8 | intro | drone and tabor; harp from bar 3, bass and tambourine from bar 5 | the spire's stairs: running steps, quickening pulse |
| 9-16 | A | recorder calls, shawm answers, over harp, bass and tabor | a chase: two voices daring each other |
| 17-24 | A' | the same, with tambourine | faster feet, the same dare |
| 25-32 | B | the leads trade single bars, in G and D | the chase turns a corner: quicker exchanges, brighter |
| 33-40 | B' | B again with tambourine shakes and the drone | breathless, ending open on E |
| 41-48 | bridge | drone, harp solo (the motif slowed down), a quiet pulse | a landing on the stairs: one deep breath |
| 49-56 | A'' | call and answer again over everything | the chase resumes at full speed |
| 57-64 | B'' | B with bells on the peaks | almost at the top |
| 65-72 | A''' | fullest: both leads together, the shawm a fourth below; everything plays | the top of the spire: both voices as one |
| 73-78 | turnaround | a falling cadence, then harp, drone and tabor wind down | a leap back down the stairs, and up again |

### Last Candle

E Phrygian, 4/4, quarter = 176. 28 bars, 38.2 s. File: `danger_last_candle.wav`.

**Motif:** E5 . F5 E5 G5 . F5 E5 | D5 . E5 F5 E5 (a stabbing half step, again and again)

| Role | Instrument |
|---|---|
| lead | shawm attacking, doubled a fifth below; the fiddle answers with nervous tremolos |
| accompaniment | lute hammering E-F in sixteenths; lute bass on every beat |
| bed | hurdy-gurdy drone on E and B |
| percussion | racing heartbeat, field drum and tabor without a pause, rolls into every section |
| colour | bells clashing E against F in the final charge |

| Bars | Section | Who plays | What the listener should feel |
|---|---|---|---|
| 1-2 | alarm | a racing heartbeat, the drone, the lute starts hammering E-F | your heart jumps: the fight has just turned against you |
| 3-10 | assault | shawm attacks the motif over hammering lute, bass and every drum | the enemy presses: fast, relentless, no room to think |
| 11-18 | counterattack | the fiddle takes the motif higher, the shawm stabs back in fifths; tambourine | you fight back, but it is not enough yet |
| 19-22 | breaking point | drums, drone and the fiddle trembling upwards; a long roll | everything tightens: one more hit and it is over |
| 23-28 | final charge | fullest: shawm in fifths, fiddle an octave up, hammering lute, all drums, clashing bells | all or nothing |

