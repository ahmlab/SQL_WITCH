"""Generate the game's placeholder chiptune sounds and battle music: python -m tools.make_sounds

Everything is synthesised from square, triangle and noise waves (like an NES sound chip), with
the standard library only, and written as 16-bit mono WAV files into assets/audio/. The output
is deterministic: running it twice gives identical files. Replace any file with your own and
point assets/audio/sounds.json at it; this script is only the starting kit.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "assets" / "audio"


# ------------------------------------------------------------------ oscillators

def square(phase: float, duty: float = 0.5) -> float:
    """A pulse wave centred on zero: a narrow pulse would otherwise push the whole signal
    off-centre (a DC offset), which wastes loudness and causes clicks."""
    return (2.0 if (phase % 1.0) < duty else 0.0) - 2.0 * duty


def triangle(phase: float) -> float:
    p = phase % 1.0
    return 4 * p - 1 if p < 0.5 else 3 - 4 * p


class Noise:
    """NES-style noise: a 15-bit linear feedback shift register, so it is repeatable."""

    def __init__(self, seed: int = 1):
        self.reg = seed or 1

    def next(self) -> float:
        bit = (self.reg ^ (self.reg >> 1)) & 1
        self.reg = (self.reg >> 1) | (bit << 14)
        return 1.0 if self.reg & 1 else -1.0


def midi(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


NOTE_NAMES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8,
              "A": 9, "A#": 10, "B": 11}


def note(name: str) -> int:
    """'A4' -> 69."""
    pitch, octave = name[:-1], int(name[-1])
    return 12 * (octave + 1) + NOTE_NAMES[pitch]


# ------------------------------------------------------------------ building blocks

def sweep(duration: float, f0: float, f1: float, wave_fn=square, duty=0.5, volume=0.5,
          attack=0.005, curve=1.0) -> list[float]:
    """A tone gliding from f0 to f1 with a linear fade-out."""
    n = int(duration * RATE)
    out, phase = [], 0.0
    for i in range(n):
        t = i / n
        freq = f0 + (f1 - f0) * (t ** curve)
        phase += freq / RATE
        env = min(1.0, i / max(1, attack * RATE)) * (1 - t)
        sample = wave_fn(phase, duty) if wave_fn is square else wave_fn(phase)
        out.append(sample * env * volume)
    return out


def noise_burst(duration: float, volume=0.5, decay=6.0, seed=1, hold=1) -> list[float]:
    """Noise with an exponential decay. `hold` repeats samples: higher = darker noise."""
    gen, n, out, value = Noise(seed), int(duration * RATE), [], 0.0
    for i in range(n):
        if i % hold == 0:
            value = gen.next()
        attack = min(1.0, i / (0.002 * RATE))      # 2 ms fade-in: no click at the start
        out.append(value * volume * attack * math.exp(-decay * i / n))
    return out


def notes(seq: list[tuple[float, float]], wave_fn=square, duty=0.5, volume=0.4,
          gap=0.0) -> list[float]:
    """Play (frequency, seconds) pairs one after the other, each with a short envelope."""
    out = []
    for freq, length in seq:
        n, phase = int(length * RATE), 0.0
        for i in range(n):
            phase += freq / RATE
            env = min(1.0, i / (0.004 * RATE)) * min(1.0, (n - i) / (0.02 * RATE))
            sample = wave_fn(phase, duty) if wave_fn is square else wave_fn(phase)
            out.append(sample * env * volume)
        out.extend([0.0] * int(gap * RATE))
    return out


def mix(*tracks: list[float]) -> list[float]:
    length = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(length)]


def write(name: str, samples: list[float]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    peak = max(1e-9, max(abs(s) for s in samples))
    gain = min(1.0, 0.9 / peak)                      # never clip
    frames = b"".join(struct.pack("<h", int(max(-1, min(1, s * gain)) * 32767))
                      for s in samples)
    with wave.open(str(OUT / name), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(frames)
    print(f"  {name:22} {len(samples) / RATE:5.2f} s")


# ------------------------------------------------------------------ sound effects

def make_effects() -> None:
    # A spell lands: a crunchy noise hit over a falling square.
    write("hit.wav", mix(noise_burst(0.16, 0.6, 9, seed=3, hold=2),
                         sweep(0.16, 320, 70, volume=0.45)))
    # A critical hit: brighter, longer, with a second impact.
    write("crit.wav", mix(noise_burst(0.32, 0.7, 6, seed=5),
                          sweep(0.32, 900, 90, duty=0.25, volume=0.4),
                          [0.0] * int(0.08 * RATE) + sweep(0.2, 500, 60, volume=0.35)))
    # Bars: HP falls in short steps down, rises up; MP is softer and rounder (triangle).
    write("hp_down.wav", notes([(midi(n), 0.045) for n in (76, 72, 69, 64, 60)],
                               duty=0.25, volume=0.35))
    write("hp_up.wav", notes([(midi(n), 0.05) for n in (64, 67, 72, 76, 79, 84)],
                             duty=0.25, volume=0.35))
    write("mp_down.wav", sweep(0.35, 1100, 260, wave_fn=triangle, volume=0.55, curve=0.6))
    write("mp_up.wav", notes([(midi(n), 0.045) for n in (72, 79, 84, 88, 91, 96)],
                             wave_fn=triangle, volume=0.5))
    # Casting: a rising shimmer.
    write("cast.wav", mix(sweep(0.28, 300, 1400, duty=0.125, volume=0.3, curve=0.5),
                          sweep(0.28, 450, 2100, wave_fn=triangle, volume=0.25, curve=0.5)))
    # Spells fizzling in the margin: a descending hiss.
    write("fizzle.wav", mix(noise_burst(0.45, 0.35, 3, seed=7, hold=1),
                            sweep(0.45, 700, 120, duty=0.125, volume=0.12)))
    # A miscast: the book puffs smoke.
    write("miscast.wav", noise_burst(0.3, 0.6, 5, seed=11, hold=6))
    # A free look: a soft page turn blip.
    write("scry.wav", notes([(midi(81), 0.04), (midi(88), 0.06)], duty=0.125, volume=0.25))
    # The Invitation: the rune glows (a bell-like pentatonic arpeggio).
    write("invitation.wav", notes([(midi(n), 0.11) for n in (72, 76, 79, 84, 88, 91)]
                                  + [(midi(96), 0.4)], wave_fn=triangle, volume=0.5))
    # Someone faints: a long slide down.
    write("faint.wav", sweep(0.7, 600, 40, duty=0.5, volume=0.4, curve=0.7))
    # Menus.
    write("confirm.wav", notes([(midi(76), 0.04), (midi(83), 0.07)], duty=0.25, volume=0.3))
    # Result jingles.
    write("victory.wav", mix(
        notes([(midi(n), d) for n, d in ((72, .12), (76, .12), (79, .12), (84, .36),
                                         (81, .12), (84, .6))], duty=0.25, volume=0.35),
        notes([(midi(n), d) for n, d in ((48, .36), (55, .36), (53, .24), (48, .6))],
              wave_fn=triangle, volume=0.45)))
    write("defeat.wav", mix(
        notes([(midi(n), d) for n, d in ((69, .3), (68, .3), (67, .3), (64, .9))],
              duty=0.5, volume=0.3),
        notes([(midi(n), d) for n, d in ((45, .6), (40, 1.2))], wave_fn=triangle,
              volume=0.45)))


# ------------------------------------------------------------------ typing and story

TYPING_SCALE = (72, 74, 76, 79, 81, 84, 86, 88)   # C major pentatonic: any order sounds good


def pluck(freq: float, duration: float, volume: float = 0.5) -> list[float]:
    """A short magical pluck: a triangle body, a bright octave sparkle and an electric crackle."""
    n, out = int(duration * RATE), []
    crackle = Noise(17)
    p1 = p2 = 0.0
    for i in range(n):
        t = i / RATE
        p1 += freq / RATE
        p2 += 2 * freq / RATE
        body = triangle(p1) * math.exp(-18 * t)
        sparkle = square(p2, 0.125) * 0.35 * math.exp(-45 * t)
        zap = crackle.next() * 0.25 * math.exp(-260 * t)
        attack = min(1.0, i / (0.001 * RATE))
        out.append((body + sparkle + zap) * attack * volume)
    return out


def make_typing_and_story() -> None:
    # One note per key: the letters of a word climb this scale, so typing plays a melody.
    for i, n in enumerate(TYPING_SCALE, start=1):
        write(f"key_{i}.wav", pluck(midi(n), 0.11))
    write("erase.wav", sweep(0.06, 700, 350, duty=0.125, volume=0.25))
    write("newline.wav", mix(noise_burst(0.16, 0.12, 2, seed=19, hold=3),
                             sweep(0.16, 400, 800, wave_fn=triangle, volume=0.25)))
    # A keyword completed (SELECT, FROM...): a quick bright chord, the rune "clicks" into place.
    write("rune.wav", mix(notes([(midi(n), 0.035) for n in (84, 88, 91)] + [(midi(96), 0.15)],
                                wave_fn=triangle, volume=0.45),
                          noise_burst(0.05, 0.12, 30, seed=23)))
    # A locked rune typed: a dull thud, the page refuses it.
    write("locked.wav", mix(sweep(0.12, 140, 60, volume=0.35),
                            noise_burst(0.1, 0.2, 12, seed=29, hold=8)))
    # The office monitor: two heartbeats, then the flat line.
    beep = lambda d: sweep(d, 988, 988, wave_fn=triangle, volume=0.35, curve=1.0)
    silence = lambda d: [0.0] * int(d * RATE)
    tone = notes([(988, 2.2)], wave_fn=triangle, volume=0.3)
    fade = 0.6 * RATE                                    # the flat line fades out slowly
    flat = [sample * min(1.0, (len(tone) - i) / fade) for i, sample in enumerate(tone)]
    write("flatline.wav", beep(0.1) + silence(0.55) + beep(0.1) + silence(0.55) + flat)
    # The Grimoire appears: a rising shimmer with sparkles.
    write("book.wav", mix(sweep(0.8, 300, 1500, wave_fn=triangle, volume=0.35, curve=0.6),
                          notes([(midi(n), 0.09) for n in (84, 88, 91, 96, 100, 103)],
                                duty=0.125, volume=0.12)))


# ------------------------------------------------------------------ battle music

BPM = 150
EIGHTH = 60 / BPM / 2
CHORDS = ["Am", "F", "C", "G"]
ROOTS = {"Am": "A2", "F": "F2", "C": "C3", "G": "G2"}
ARPS = {"Am": ("A4", "C5", "E5"), "F": ("F4", "A4", "C5"),
        "C": ("C5", "E5", "G5"), "G": ("G4", "B4", "D5")}
# Lead melody, one bar per chord, eight eighth notes per bar. "-" holds, "." rests.
MELODY_A = ["A4 - C5 E5 D5 C5 A4 -", "F4 - A4 C5 B4 A4 F4 -",
            "E4 G4 C5 - E5 - D5 C5", "D5 - B4 - G4 A4 B4 -"]
MELODY_B = ["E5 - E5 D5 E5 - A5 -", "F5 - E5 D5 C5 - A4 -",
            "G4 - C5 - E5 - G5 -", "F5 E5 D5 B4 G4 - - ."]
SONG = MELODY_A + MELODY_B + MELODY_A + MELODY_B          # 16 bars, about 25 seconds


def lead_events(bars: list[str]) -> list[tuple[int, int, int]]:
    """(start eighth, length in eighths, midi note) for the melody."""
    events, step = [], 0
    for bar in bars:
        for token in bar.split():
            if token == "-" and events:
                start, length, n = events[-1]
                events[-1] = (start, length + 1, n)
            elif token not in ("-", "."):
                events.append((step, 1, note(token)))
            step += 1
    return events


def render_voice(total: int, events, wave_fn, duty, volume, release=0.03) -> list[float]:
    out = [0.0] * total
    for start, length, n in events:
        begin = int(start * EIGHTH * RATE)
        size = int(length * EIGHTH * RATE)
        freq, phase = midi(n), 0.0
        for i in range(size):
            if begin + i >= total:
                break
            phase += freq / RATE
            env = min(1.0, i / (0.004 * RATE)) * (0.75 + 0.25 * math.exp(-6 * i / size))
            env *= min(1.0, (size - i) / (release * RATE))
            sample = wave_fn(phase, duty) if wave_fn is square else wave_fn(phase)
            out[begin + i] += sample * env * volume
    return out


def make_music() -> None:
    bars = len(SONG)
    total = int(bars * 8 * EIGHTH * RATE)
    lead = render_voice(total, lead_events(SONG), square, 0.25, 0.22)

    bass_events, arp_events = [], []
    for bar in range(bars):
        chord = CHORDS[bar % 4]
        root = note(ROOTS[chord])
        for step, n in enumerate((root, root, root + 12, root, root, root + 12, root, root + 7)):
            bass_events.append((bar * 8 + step, 1, n))
        tones = ARPS[chord]
        for sixteenth in range(16):           # arpeggio in sixteenths, an octave of shimmer
            arp_events.append((bar * 8 + sixteenth / 2, 0.5, note(tones[sixteenth % 3]) + 12))
    bass = render_voice(total, bass_events, triangle, 0.5, 0.32, release=0.01)
    arp = render_voice(total, arp_events, square, 0.125, 0.06, release=0.005)

    drums = [0.0] * total
    hat, snare = Noise(9), Noise(13)
    for step in range(bars * 8):
        begin = int(step * EIGHTH * RATE)
        if step % 4 == 0:                       # kick on beats 1 and 3: a falling sine thump
            for i in range(int(0.12 * RATE)):
                t = i / RATE
                drums[begin + i] += math.sin(2 * math.pi * (110 - 500 * t) * t) \
                    * math.exp(-28 * t) * 0.5
        if step % 4 == 2:                       # snare on beats 2 and 4
            for i in range(int(0.14 * RATE)):
                attack = min(1.0, i / (0.001 * RATE))
                drums[begin + i] += snare.next() * attack * math.exp(-22 * i / RATE) * 0.22
        for i in range(int(0.03 * RATE)):       # closed hat on every eighth
            if begin + i < total:
                attack = min(1.0, i / (0.001 * RATE))
                drums[begin + i] += hat.next() * attack * math.exp(-120 * i / RATE) * 0.07

    write("battle_theme.wav", [a + b + c + d for a, b, c, d in zip(lead, bass, arp, drums)])


def main() -> None:
    print(f"Writing sounds to {OUT}")
    make_effects()
    make_typing_and_story()
    make_music()


if __name__ == "__main__":
    main()
