"""Generate the battle music: python -m tools.make_music [--only NAME] [--sheet]

Five medieval battle themes and one danger theme, synthesised with the standard library only
and written as 16-bit mono WAV files into assets/audio/. The output is deterministic: two runs
give byte-identical files.

How it works, from small to big:
- Instruments that suggest real ones: a plucked lute and harp (Karplus-Strong strings), a
  recorder, a shawm and a fiddle (wavetables with vibrato and breath), a hurdy-gurdy drone,
  a tabor, a field drum, a tambourine, a bell and a heartbeat.
- Scores are written as text, one token per eighth note ("D5", "-" holds, "." rests,
  "D5+E5" two sixteenths, "E5>D5" a grace note into D5). An Arrangement places lines, chords,
  drones and drum patterns bar by bar, section by section.
- Rendering is circular: whatever rings past the last bar (a lute note, the echo) is added to
  the first bars, so the loop seam is inaudible.
- Every track is brought to the same loudness, then gently limited (never clipped).

Musical rule: no C#, D#/Eb or G#/Ab anywhere. The typing sounds play C major pentatonic on
every keystroke, and those three pitches would clash with them. tests/test_music.py checks
the note data of every track.

Never imported by the game: it only writes files.
"""

from __future__ import annotations

import argparse
import math
import struct
import wave
from dataclasses import dataclass, field
from functools import lru_cache

from tools.make_sounds import OUT, RATE, Noise, midi

FORBIDDEN = {1, 3, 8}                       # pitch classes C#, D#/Eb, G#/Ab
TAIL_S = 4.0                                # rendered past the end, then folded onto the start
TARGET_RMS = {"battle": 0.115, "danger": 0.085}
LIMIT = 0.92                                # soft limiter ceiling (full scale is 1.0)

# ------------------------------------------------------------------ pitch

LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MODES = {
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
}


def pitch(name: str) -> int:
    """'D5' -> 74, 'Bb4' -> 70, 'F#5' -> 78."""
    letter, accidentals, octave = name[0], name[1:-1], int(name[-1])
    return 12 * (octave + 1) + LETTERS[letter] + accidentals.count("#") - accidentals.count("b")


def scale(tonic: str, mode: str) -> tuple[int, ...]:
    """The pitch classes of a mode, sorted from C."""
    root = LETTERS[tonic[0]] + tonic[1:].count("#") - tonic[1:].count("b")
    return tuple(sorted((root + step) % 12 for step in MODES[mode]))


def diatonic(m: int, steps: int, pcs: tuple[int, ...], perfect: bool = False) -> int:
    """Move a note by scale steps. With `perfect`, a doubling that would land a tritone away
    becomes a perfect fourth or fifth instead (medieval doubling is in perfect intervals)."""
    octave, degree = divmod(pcs.index(m % 12) + steps, len(pcs))
    moved = (m // 12 + octave) * 12 + pcs[degree]
    if perfect and abs(moved - m) % 12 == 6 and steps:
        return diatonic(m, steps + (1 if steps < 0 else -1), pcs)
    return moved


CHORDS = {"": (0, 4, 7), "m": (0, 3, 7), "5": (0, 7, 12)}


def chord(name: str, octave: int) -> list[int]:
    """'Dm' in octave 3 -> D3 F3 A3."""
    root = name[0] + ("b" if name[1:2] == "b" else "#" if name[1:2] == "#" else "")
    kind = name[len(root):]
    base = pitch(root + str(octave))
    return [base + step for step in CHORDS[kind]]


# ------------------------------------------------------------------ small DSP helpers

def lowpass_coef(cutoff: float) -> float:
    return 1 - math.exp(-2 * math.pi * cutoff / RATE)


def lowpass(samples: list[float], cutoff: float, circular: bool = False) -> list[float]:
    """One-pole low-pass. Circular: warmed up on the end, so the loop seam stays smooth."""
    a, y = lowpass_coef(cutoff), 0.0
    if circular:
        for s in samples[-2048:]:
            y += a * (s - y)
    out = []
    for s in samples:
        y += a * (s - y)
        out.append(y)
    return out


def fade_out(samples: list[float], seconds: float) -> list[float]:
    """End at silence: a sound cut while it still rings is a click."""
    n = len(samples)
    k = min(n, int(seconds * RATE))
    for i in range(n - k, n):
        samples[i] *= (n - i) / k
    return samples


def jitter(i: int, spread: float) -> float:
    """A deterministic small offset in [-spread, spread]: scores played by people waver."""
    x = (i * 2654435761 + 12345) & 0xFFFFFFFF
    return ((x / 0xFFFFFFFF) * 2 - 1) * spread


# ------------------------------------------------------------------ instruments

TABLE = 2048


@lru_cache(maxsize=None)
def wavetable(timbre: str, harmonics: int) -> tuple[float, ...]:
    """One period of a timbre, built from its harmonics (band-limited: no aliasing)."""
    weight = TIMBRES[timbre]
    table = [sum(weight(k) * math.sin(2 * math.pi * k * i / TABLE)
                 for k in range(1, harmonics + 1)) for i in range(TABLE)]
    peak = max(abs(v) for v in table) or 1.0
    return tuple(v / peak for v in table)


TIMBRES = {
    # A recorder is almost a sine: a pure, breathy tone.
    "recorder": lambda k: {1: 1.0, 2: 0.10, 3: 0.09, 4: 0.025, 5: 0.015}.get(k, 0.0),
    # A shawm is a double reed: a narrow pulse, strong in the middle harmonics (nasal).
    "shawm": lambda k: abs(math.sin(math.pi * k * 0.27)) / k * (1.5 if 3 <= k <= 7 else 1.0),
    # A fiddle is a bowed string: a sawtooth with a body resonance around harmonics 2 to 5.
    "fiddle": lambda k: 1.0 / k * (1.5 if 2 <= k <= 5 else 0.8),
    # A hurdy-gurdy drone buzzes: many harmonics, slowly falling.
    "gurdy": lambda k: 1.0 / (k ** 1.1),
}


def _harmonics(freq: float, wanted: int) -> int:
    return max(1, min(wanted, int(9500 / freq)))


def sustained(freq: float, seconds: float, timbre: str, harmonics: int, attack: float,
              release: float, vib_rate: float = 0.0, vib_depth: float = 0.0,
              vib_delay: float = 0.0, detune: float = 0.0, breath: float = 0.0,
              chiff: float = 0.0, cutoff: float | None = None, tremolo: float = 0.0,
              trem_rate: float = 0.0, seed: int = 1) -> list[float]:
    """A held tone from a wavetable: envelope, delayed vibrato, a second detuned voice and
    breath noise. The vibrato is updated every 32 samples (plenty, and fast in pure Python)."""
    table = wavetable(timbre, _harmonics(freq, harmonics))
    n = int((seconds + release) * RATE)
    held = int(seconds * RATE)
    out = [0.0] * n
    step = freq * TABLE / RATE
    voices = [(step, 0.0)] if not detune else \
        [(step * 2 ** (detune / 1200), 0.0), (step * 2 ** (-detune / 1200), TABLE * 0.37)]
    noise, nz = Noise(seed), 0.0
    na = lowpass_coef(3500)
    for v_step, v_phase in voices:
        ph, mod = v_phase, 1.0
        for i in range(n):
            if i % 32 == 0:
                t = i / RATE
                ramp = min(1.0, max(0.0, (t - vib_delay) / 0.25)) if vib_depth else 0.0
                mod = 1.0 + vib_depth * ramp * math.sin(2 * math.pi * vib_rate * t)
            ph += v_step * mod
            out[i] += table[int(ph) & (TABLE - 1)]
    gain = 1.0 / len(voices)
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / attack) if attack else 1.0
        if i >= held:
            env *= max(0.0, 1.0 - (i - held) / (release * RATE))
        if tremolo:
            env *= 1.0 - tremolo * (0.5 + 0.5 * math.sin(2 * math.pi * trem_rate * t))
        sample = out[i] * gain
        if breath or chiff:
            nz += na * (noise.next() - nz)
            sample += nz * (breath + chiff * math.exp(-t / 0.025))
        out[i] = sample * env
    return lowpass(out, cutoff) if cutoff else out


def plucked(freq: float, ring: float, t60: float, bright: float, seed: int) -> list[float]:
    """Karplus-Strong: a burst of noise circulating in a delay line one period long. The
    averaging filter dulls it like a real string; an all-pass filter tunes the fraction of a
    sample the integer delay line cannot hold."""
    period = RATE / freq
    n_delay = max(2, int(period - 0.5 - 0.1))
    frac = period - 0.5 - n_delay                       # in [0.1, 1.1)
    c = (1 - frac) / (1 + frac)
    g = 10 ** (-3 / (freq * t60))                       # loss per trip around the loop
    noise = Noise(seed)
    burst, y = [], 0.0
    a = lowpass_coef(1200 + 7000 * bright)
    for _ in range(n_delay):                            # the pluck: brighter = harder
        y += a * (noise.next() - y)
        burst.append(y)
    mean = sum(burst) / len(burst)
    line = [b - mean for b in burst]
    n = int(ring * RATE)
    out = [0.0] * n
    idx, last, ap_x, ap_y = 0, 0.0, 0.0, 0.0
    for i in range(n):
        x = line[idx]
        out[i] = x
        avg = g * 0.5 * (x + last)
        last = x
        ap = c * avg + ap_x - c * ap_y                  # fractional delay (all-pass)
        ap_x, ap_y = avg, ap
        line[idx] = ap
        idx = (idx + 1) % n_delay
    fade = int(0.03 * RATE)
    for i in range(max(0, n - fade), n):                # never stop with a click
        out[i] *= (n - i) / fade
    for i in range(min(n, 22)):                         # nor start with one
        out[i] *= i / 22
    return out


def bell(freq: float) -> list[float]:
    """A bell: a sine and inharmonic partials, each fading at its own speed."""
    partials = ((1.0, 1.0, 1.7), (2.76, 0.42, 0.75), (5.40, 0.20, 0.38), (8.93, 0.08, 0.2))
    n = int(2.6 * RATE)
    out = [0.0] * n
    for ratio, amp, decay in partials:
        f = freq * ratio
        if f > 10000:
            continue
        w = 2 * math.pi * f / RATE
        k = math.exp(-1 / (decay * RATE))
        env = amp
        for i in range(n):
            out[i] += math.sin(w * i) * env
            env *= k
    for i in range(min(n, 40)):
        out[i] *= i / 40
    return fade_out(out, 0.6)


@lru_cache(maxsize=None)
def render_note(inst: str, m: int, seconds: float, variant: int) -> tuple[float, ...]:
    """One note of an instrument, at full velocity. Cached: a tune repeats its notes."""
    f = midi(m)
    if inst in ("lute", "lutebass"):
        bass = inst == "lutebass"
        ring = min(seconds + (0.5 if bass else 0.35), 2.0 if bass else 1.6)
        return tuple(plucked(f, ring, 2.2 if bass else 1.3, 0.35 if bass else 0.6, 7 + variant))
    if inst == "harp":
        return tuple(plucked(f, min(seconds + 1.1, 2.8), 2.8, 0.3, 11 + variant))
    if inst == "bell":
        return tuple(bell(f))
    if inst == "recorder":
        return tuple(sustained(f, seconds, "recorder", 5, 0.03, 0.07, vib_rate=5.0,
                               vib_depth=0.004, vib_delay=0.2, breath=0.035, chiff=0.18,
                               seed=3 + variant))
    if inst == "shawm":
        return tuple(sustained(f, seconds, "shawm", 14, 0.02, 0.05, vib_rate=6.0,
                               vib_depth=0.003, vib_delay=0.25, detune=5, breath=0.02,
                               cutoff=3200, seed=5 + variant))
    if inst == "fiddle":
        return tuple(sustained(f, seconds, "fiddle", 12, 0.06, 0.08, vib_rate=5.5,
                               vib_depth=0.006, vib_delay=0.15, detune=3, breath=0.012,
                               cutoff=4200, seed=9 + variant))
    if inst == "gurdy":
        return tuple(sustained(f, seconds, "gurdy", 10, 0.45, 0.5, detune=4, cutoff=1800,
                               tremolo=0.08, trem_rate=0.35, seed=13))
    if inst == "gurdy_tremble":                       # the danger drone: it trembles
        return tuple(sustained(f, seconds, "gurdy", 8, 0.6, 0.6, vib_rate=0.4,
                               vib_depth=0.002, detune=6, cutoff=1200, tremolo=0.3,
                               trem_rate=4.7, seed=17))
    raise ValueError(f"unknown instrument {inst!r}")


@lru_cache(maxsize=None)
def instrument_gain(inst: str) -> float:
    """Make velocity 1 equally loud on every instrument: a recorder (nearly a sine) is far
    louder than a shawm at the same peak. Measured once on a reference note, A4 for half a
    second (A3 for the bass lute, which never plays that high)."""
    m = 57 if inst in ("lutebass", "gurdy", "gurdy_tremble") else 69
    sample = render_note(inst, m, 0.5, 0)[:int(0.5 * RATE)]
    rms = math.sqrt(sum(v * v for v in sample) / len(sample))
    return 0.3 / rms if rms else 1.0


# ------------------------------------------------------------------ percussion

def _thump(f0: float, f1: float, drop: float, decay: float, seconds: float) -> list[float]:
    n, ph, out = int(seconds * RATE), 0.0, []
    for i in range(n):
        t = i / RATE
        ph += 2 * math.pi * (f1 + (f0 - f1) * math.exp(-drop * t)) / RATE
        out.append(math.sin(ph) * math.exp(-decay * t) * min(1.0, i / 30))
    return out


def _skin(seconds: float, decay: float, cutoff: float, seed: int, high: bool = False) -> list[float]:
    noise, n = Noise(seed), int(seconds * RATE)
    raw = [noise.next() for _ in range(n)]
    soft = lowpass(raw, cutoff)
    shaped = [r - s for r, s in zip(raw, soft)] if high else soft
    return [v * math.exp(-decay * i / RATE) * min(1.0, i / 20) for i, v in enumerate(shaped)]


def _mix(*parts: tuple[float, list[float]]) -> list[float]:
    n = max(len(p) for _, p in parts)
    out = [0.0] * n
    for gain, part in parts:
        for i, v in enumerate(part):
            out[i] += gain * v
    return out


@lru_cache(maxsize=None)
def render_hit(kind: str, variant: int) -> tuple[float, ...]:
    return tuple(fade_out(list(_hit(kind, variant)), 0.02))


def _hit(kind: str, variant: int) -> tuple[float, ...]:
    if kind == "dum":                                  # tabor, low: the skin's belly
        return tuple(_mix((1.0, _thump(150, 62, 28, 8, 0.42)),
                          (0.35, _skin(0.12, 40, 900, 21 + variant))))
    if kind == "tek":                                  # tabor, rim: dry and short
        return tuple(_mix((0.5, _thump(340, 250, 40, 34, 0.14)),
                          (0.55, _skin(0.1, 55, 4200, 23 + variant))))
    if kind == "kick":                                 # the march's bass drum
        return tuple(_mix((1.0, _thump(110, 46, 18, 6.5, 0.55)),
                          (0.25, _skin(0.1, 35, 600, 25 + variant))))
    if kind == "snare":                                # the field drum: tone and snares
        return tuple(_mix((0.45, _thump(210, 180, 20, 22, 0.2)),
                          (0.75, _skin(0.32, 14, 6500, 27 + variant, high=True))))
    if kind == "jingle":                               # tambourine: bright, ringing jingles
        jingle = _skin(0.2, 18, 5000, 29 + variant, high=True)
        return tuple(v * (0.75 + 0.25 * math.cos(2 * math.pi * 31 * i / RATE))
                     for i, v in enumerate(jingle))
    if kind == "shake":                                # tambourine shaken: a swell
        shake = _skin(0.32, 7, 5000, 31 + variant, high=True)
        n = len(shake)
        return tuple(v * min(1.0, i / (0.06 * RATE)) * 0.8 for i, v in enumerate(shake[:n]))
    if kind == "heart":                                # a muffled heartbeat
        return tuple(_mix((1.0, _thump(85, 42, 20, 9, 0.5)),
                          (0.15, _skin(0.08, 40, 400, 33 + variant))))
    raise ValueError(f"unknown hit {kind!r}")


KITS = {
    "tabor": {"D": ("dum", 1.0), "d": ("dum", 0.55), "T": ("tek", 1.0), "t": ("tek", 0.55),
              "R": ("tek", 0.6)},
    "field": {"K": ("kick", 1.0), "k": ("kick", 0.55), "S": ("snare", 1.0), "s": ("snare", 0.45),
              "R": ("snare", 0.7)},
    "tamb": {"J": ("jingle", 1.0), "j": ("jingle", 0.5), "W": ("shake", 1.0), "w": ("shake", 0.5)},
    "heart": {"H": ("heart", 1.0), "h": ("heart", 0.6)},
}

# Which mix bus each instrument feeds, and how much of it goes to the echo.
BUS = {"recorder": "lead", "shawm": "lead", "fiddle": "lead", "lute": "pluck", "harp": "pluck",
       "lutebass": "bass", "gurdy": "drone", "gurdy_tremble": "drone", "bell": "bell",
       "tabor": "perc", "field": "perc", "tamb": "perc", "heart": "perc"}
# The mix, as each bus's loudness relative to the lead (dB, measured while the bus plays).
# The lead is clearly on top, the bass is felt more than heard, percussion supports.
LEVELS = {"lead": 0.0, "pluck": -8.0, "bass": -9.0, "drone": -15.0, "bell": -9.0, "perc": -8.0}
ECHO_SEND = {"lead": 0.25, "pluck": 0.12, "bell": 0.4, "bass": 0.0, "drone": 0.0, "perc": 0.04}


# ------------------------------------------------------------------ scores

GRACE = 0.25                     # a grace note lasts a quarter of an eighth


def parse(text: str, slots: int) -> tuple[list[list], int]:
    """Bars of tokens -> [start, length, midi, is_grace] in eighths, and the number of bars."""
    bars = [bar.split() for bar in text.split("|") if bar.strip()]
    events: list[list] = []
    t = 0.0
    for number, bar in enumerate(bars, start=1):
        if len(bar) != slots:
            raise ValueError(f"bar {number} has {len(bar)} slots, needs {slots}: {' '.join(bar)}")
        for token in bar:
            parts = token.split("+")
            step = 1.0 / len(parts)
            for part in parts:
                _token(part, t, step, events)
                t += step
    return events, len(bars)


def _token(token: str, t: float, step: float, events: list[list]) -> None:
    if token == ".":
        return
    if token == "-":
        if events and abs(events[-1][0] + events[-1][1] - t) < 1e-9:
            events[-1][1] += step                       # hold the previous note
        return
    if ">" in token:                                    # a grace note into the main note
        grace, main = token.split(">")
        g = min(GRACE, step / 3)
        events.append([t, g, pitch(grace), True])
        events.append([t + g, step - g, pitch(main), False])
        return
    events.append([t, step, pitch(token), False])


@dataclass
class Section:
    name: str
    first: int                   # first bar, counting from 0
    bars: int
    roles: str                   # who plays, for the score sheet
    feel: str                    # what the listener should feel


@dataclass
class Arrangement:
    """A whole track: notes, hits and sections, measured in eighth notes."""
    key: str
    title: str
    mode: str
    metre: str
    tempo: str
    eighth: float                # seconds per eighth note
    slots: int                   # eighths per bar
    beat: int                    # eighths per beat (3 in 6/8, 2 in 3/4 and 4/4)
    pcs: tuple[int, ...]
    kind: str = "battle"
    levels: dict[str, float] = field(default_factory=lambda: dict(LEVELS))
    motif: str = ""
    instruments: dict[str, str] = field(default_factory=dict)
    notes: list[tuple] = field(default_factory=list)     # (inst, start, length, midi, vel)
    hits: list[tuple] = field(default_factory=list)      # (kit, kind, start, vel)
    sections: list[Section] = field(default_factory=list)
    bars: int = 0

    # ------------------------------------------------------------ building

    def section(self, name: str, bars: int, roles: str, feel: str) -> int:
        self.sections.append(Section(name, self.bars, bars, roles, feel))
        self.bars += bars
        return self.bars - bars

    def play(self, inst: str, bar: int, text: str, vel: float = 1.0, octave: int = 0,
             double: int = 0) -> None:
        """A melodic line from `bar`. `double` moves it by scale steps (a parallel voice)."""
        events, _ = parse(text, self.slots)
        for start, length, m, grace in events:
            m += 12 * octave
            if double:
                m = diatonic(m, double, self.pcs, perfect=True)
            accent = 1.0 if (start % self.beat) < 1e-9 else 0.86
            self.notes.append((inst, bar * self.slots + start, length, m,
                               vel * accent * (0.7 if grace else 1.0)))

    def chords(self, inst: str, bar: int, names: str, pattern: str, octave: int = 3,
               vel: float = 1.0) -> None:
        """Chords bar by bar ("Dm C" or "Dm,C" for two per bar), played to a pattern of
        tone indexes per eighth: 0 1 2 root, third, fifth; 3 4 5 an octave up; 9 the ninth;
        "012" strums; "." rests."""
        tokens = pattern.split()
        for b, name in enumerate(names.replace("|", " ").split()):
            parts = name.split(",")
            span = self.slots // len(parts)
            for p, part in enumerate(parts):
                tones = chord(part, octave)
                pool = tones + [t + 12 for t in tones] + [t + 24 for t in tones]
                ninth = diatonic(tones[0] + 12, 1, self.pcs)
                start = (bar + b) * self.slots + p * span
                slice_ = tokens[p * span:(p + 1) * span]
                onsets = [i for i, tok in enumerate(slice_) if tok != "."]
                for k, i in enumerate(onsets):
                    end = onsets[k + 1] if k + 1 < len(onsets) else span
                    for s, digit in enumerate(slice_[i]):
                        m = ninth if digit == "9" else pool[int(digit)]
                        self.notes.append((inst, start + i + 0.06 * s, end - i, m,
                                           vel * (1.0 if i % self.beat == 0 else 0.8)))

    def drone(self, bar: int, bars: int, names: list[str], vel: float = 1.0,
              inst: str = "gurdy") -> None:
        for name in names:
            self.notes.append((inst, bar * self.slots, bars * self.slots, pitch(name), vel))

    def drums(self, kit: str, bar: int, text: str, vel: float = 1.0) -> None:
        """A drum pattern, one token per eighth: letters from KITS, "R" a roll, "." rest."""
        bars = [b.split() for b in text.split("|") if b.strip()]
        for b, tokens in enumerate(bars):
            if len(tokens) != self.slots:
                raise ValueError(f"drum bar {b + 1} has {len(tokens)} slots: {tokens}")
            for i, token in enumerate(tokens):
                start = (bar + b) * self.slots + i
                parts = token.split("+")
                for p, part in enumerate(parts):
                    at = start + p / len(parts)
                    if part == ".":
                        continue
                    kind, v = KITS[kit][part]
                    if part == "R":                     # a roll: four quick, rising strokes
                        for r in range(4):
                            self.hits.append((kit, kind, at + r / (4 * len(parts)),
                                              vel * v * (0.45 + 0.18 * r)))
                    else:
                        self.hits.append((kit, kind, at, vel * v))

    # ------------------------------------------------------------ reading

    @property
    def seconds(self) -> float:
        return self.bars * self.slots * self.eighth

    def pitches(self) -> set[int]:
        return {note[3] for note in self.notes}


# ------------------------------------------------------------------ rendering

def _place(bus: list[float], at: float, sample: tuple[float, ...], gain: float) -> None:
    start = int(at * RATE)
    end = min(len(bus), start + len(sample))
    for i in range(start, end):
        bus[i] += sample[i - start] * gain


def _rms(x: list[float]) -> float:
    active = [v for v in x if abs(v) > 1e-4]
    return math.sqrt(sum(v * v for v in active) / len(active)) if active else 0.0


def echo(send: list[float], delay: float, feedback: float, length: int) -> list[float]:
    """A single feedback echo with a darker repeat each time. Run over two laps of the
    loop, keeping the second: the echo of the last bar then rings into the first one."""
    d = int(delay * RATE)
    lap = send[:length]
    y = [0.0] * (2 * length)
    a, z = lowpass_coef(2800), 0.0
    for n in range(2 * length):
        fed = y[n - d] if n >= d else 0.0
        z += a * (fed - z)
        y[n] = (lap[(n - d) % length] if n >= d else 0.0) + feedback * z
    return y[length:]


def render(arr: Arrangement, bars: int | None = None, report: bool = False) -> list[float]:
    """Render an arrangement to samples (all of it, or only its first `bars`, for tests)."""
    bars = bars or arr.bars
    length = int(bars * arr.slots * arr.eighth * RATE)
    size = length + int(TAIL_S * RATE)
    buses = {name: [0.0] * size for name in LEVELS}
    limit = bars * arr.slots
    for i, (inst, start, dur, m, vel) in enumerate(arr.notes):
        if start >= limit:
            continue
        seconds = round(dur * arr.eighth, 3)
        sample = render_note(inst, m, seconds, i % 2)
        at = max(0.0, start * arr.eighth + jitter(i, 0.006 if BUS[inst] == "lead" else 0.004))
        _place(buses[BUS[inst]], at, sample,
               vel * instrument_gain(inst) * (1 + jitter(i + 7, 0.06)))
    for i, (kit, kind, start, vel) in enumerate(arr.hits):
        if start >= limit:
            continue
        at = max(0.0, start * arr.eighth + jitter(i + 99, 0.005))
        _place(buses["perc"], at, render_hit(kind, i % 3), vel * (1 + jitter(i + 3, 0.08)))
    for bus in buses.values():                       # fold the tail onto the beginning
        for i in range(length, size):
            bus[i - length] += bus[i]
        del bus[length:]
    # Balance: every bus is set to its level relative to the lead (or to the loudest bus).
    loudness = {name: _rms(bus) for name, bus in buses.items()}
    reference = loudness["lead"] or max(loudness.values())
    gains = {name: (10 ** (arr.levels[name] / 20) * reference / level if level else 0.0)
             for name, level in loudness.items()}
    if report:
        print("      " + "  ".join(f"{name} {20 * math.log10(level):.0f}dB"
                                   for name, level in loudness.items() if level))
    mix = [0.0] * length
    send = [0.0] * length
    for name, bus in buses.items():
        g, e = gains[name], ECHO_SEND[name]
        for i, v in enumerate(bus):
            mix[i] += v * g
            send[i] += v * g * e
    wet = echo(send, 3 * arr.eighth, 0.33, length)
    mix = [m + 0.5 * w for m, w in zip(mix, wet)]
    mix = lowpass(mix, 7500, circular=True)            # soften the last harsh edges
    return master(mix, TARGET_RMS[arr.kind])


def master(mix: list[float], target: float) -> list[float]:
    """Remove any DC, bring the track to the target loudness, and limit the peaks softly."""
    mean = sum(mix) / len(mix)
    mix = [v - mean for v in mix]
    rms = math.sqrt(sum(v * v for v in mix) / len(mix)) or 1.0
    gain = target / rms
    knee = 0.75 * LIMIT
    out = []
    for v in mix:
        v *= gain
        a = abs(v)
        if a > knee:                                   # above the knee: bend, never clip
            a = knee + (LIMIT - knee) * math.tanh((a - knee) / (LIMIT - knee))
            v = math.copysign(a, v)
        out.append(v)
    return out


def to_bytes(samples: list[float]) -> bytes:
    return b"".join(struct.pack("<h", int(round(max(-1.0, min(1.0, s)) * 32767)))
                    for s in samples)


def write(name: str, samples: list[float]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = to_bytes(samples)
    with wave.open(str(OUT / name), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(data)
    return len(data) + 44


# ------------------------------------------------------------------ 1. Glade Jig

def glade_jig() -> Arrangement:
    """D Dorian, 6/8: playful and bouncing. Recorder over lute, tabor underneath."""
    arr = Arrangement("glade_jig", "Glade Jig", "D Dorian", "6/8", "dotted quarter = 126",
                      60 / 126 / 3, 6, 3, scale("D", "dorian"))
    arr.motif = "D5 A4 D5 E5 | F5 E5 D5 C5 (a hop down a fourth and back, then a falling answer)"
    arr.instruments = {"lead": "recorder (A'' adds a second recorder a fourth below)",
                       "accompaniment": "lute arpeggios; lute bass on the beats",
                       "bed": "hurdy-gurdy drone on D and A", "percussion": "tabor, tambourine",
                       "colour": "bell on the strong bars of the last section"}
    A = ("D5 - A4 D5 - E5 | G5>F5 - E5 D5 - C5 | C5 - G4 C5 - D5 | E5 - D5 C5 - A4 |"
         "D5 - A4 D5 - E5 | F5 - G5 A5 - F5 | G5 - E5 C5 - E5 | D5 - - D5 - .")
    A_CH = "Dm Dm C C,Am Dm F C Dm"
    A2 = ("D5 - A4 D5 - E5 | G5>F5 - E5 D5 - C5 | C5 - G4 C5 - D5 | E5 - D5 C5 - A4 |"
          "D5 - A4 D5 - E5 | F5 - G5 A5 - C6 | B5 - G5 E5 - C5 | D5 - - - - .")
    A2_CH = "Dm Dm C C,Am Dm F G,C Dm"
    B = ("A5 - G5 F5 - G5 | A5 - C6 A5 - - | G5 - F5 E5 - F5 | G5 - - E5 - C5 |"
         "F5 - E5 D5 - E5 | F5 - D5 B4 - G4 | A4 - B4 C5 - E5 | D5 - - . . A4")
    B_CH = "F F C C Dm G Am Dm"
    B2 = ("A5 - G5 F5 - G5 | A5 - C6 A5 - - | G5 - F5 E5 - F5 | G5 - - E5 - C5 |"
          "F5 - E5 D5 - E5 | F5 - G5 A5 - B5 | C6 - B5 A5 - G5 | A5 - - - - .")
    B2_CH = "F F C C Dm G C Am"
    BRIDGE = ("D4 - - A3 - - | D4 - - E4 - - | F4 - - E4 - D4 | C4 - - - - - |"
              "D4 - - A3 - - | F4 - - G4 - - | A4 - - G4 - E4 | D4 - - - - .")
    ARP = "0 2 3 4 3 2"
    BASS = "0 . . 2 . ."
    JIG = "D . t d . t"
    FILL = "D t+t t D+t t+t R"

    def jig(bar, bars, fill=True, vel=1.0):
        arr.drums("tabor", bar, " | ".join([JIG] * (bars - 1) + [FILL if fill else JIG]), vel)

    s = arr.section("intro", 6, "drone, tabor; lute arpeggios from bar 3, bass from bar 5",
                    "a clearing wakes up: something is about to start dancing")
    arr.drone(s, 6, ["D3", "A3"])
    jig(s, 6, vel=0.8)
    arr.chords("lute", s + 2, "Dm Dm C Dm", ARP, 3, 0.7)
    arr.chords("lutebass", s + 4, "Dm Dm", BASS, 2)
    s = arr.section("A", 8, "recorder states the motif over lute, bass and tabor",
                    "the tune arrives: cheeky, light on its feet")
    arr.play("recorder", s, A)
    arr.chords("lute", s, A_CH, ARP, 3, 0.8)
    arr.chords("lutebass", s, A_CH, BASS, 2)
    arr.drone(s, 8, ["D3", "A3"], 0.7)
    jig(s, 8)
    s = arr.section("A'", 8, "recorder with a new ending; tambourine joins",
                    "the same tune, a little bolder, reaching higher at the end")
    arr.play("recorder", s, A2)
    arr.chords("lute", s, A2_CH, ARP, 3, 0.8)
    arr.chords("lutebass", s, A2_CH, BASS, 2)
    arr.drone(s, 8, ["D3", "A3"], 0.7)
    jig(s, 8)
    arr.drums("tamb", s, " | ".join(["j . . J . ."] * 8), 0.8)
    s = arr.section("B", 8, "recorder high, lute bass walks, tambourine shakes",
                    "a change of light: brighter, in F major, singing more than dancing")
    arr.play("recorder", s, B)
    arr.chords("lute", s, B_CH, "0 2 3 . 3 2", 3, 0.75)
    arr.chords("lutebass", s, B_CH, "0 . 2 0 . 2", 2)
    jig(s, 8)
    arr.drums("tamb", s, " | ".join(["W . . j . ."] * 8), 0.7)
    s = arr.section("B'", 8, "B again, climbing to C6 at the end; drone returns",
                    "lifted up: the phrase climbs and hangs on A, unresolved")
    arr.play("recorder", s, B2)
    arr.chords("lute", s, B2_CH, ARP, 3, 0.8)
    arr.chords("lutebass", s, B2_CH, "0 . 2 0 . 2", 2)
    arr.drone(s + 4, 4, ["D3", "A3"], 0.6)
    jig(s, 8)
    s = arr.section("bridge", 8, "drone and a lute solo (the motif slowed down); soft tabor",
                    "a breath: the dance stops and the lute remembers the tune")
    arr.drone(s, 8, ["D3", "A3"])
    arr.play("lute", s, BRIDGE, 1.0)
    arr.drums("tabor", s, " | ".join(["d . . . . ."] * 7 + ["D . t D t R"]), 0.7)
    arr.play("bell", s, ". . . . . . | . . . . . . | . . . . . . | A5 - - - - - |"
                        ". . . . . . | . . . . . . | . . . . . . | D6 - - - - -", 0.6)
    s = arr.section("A''", 8, "fullest: two recorders in fourths, lute, bass, tabor, "
                    "tambourine, bells", "everyone dances: the tune at its fullest")
    arr.play("recorder", s, A)
    arr.play("recorder", s, A, 0.55, double=-3)
    arr.chords("lute", s, A_CH, ARP, 3, 0.85)
    arr.chords("lutebass", s, A_CH, BASS, 2)
    arr.drone(s, 8, ["D3", "A3"], 0.7)
    jig(s, 8)
    arr.drums("tamb", s, " | ".join(["J . j J . j"] * 8), 0.8)
    arr.play("bell", s, "D6 - - - - - | . . . . . . | . . . . . . | . . . . . . |"
                        "A5 - - - - - | . . . . . . | . . . . . . | . . . . . .", 0.5)
    s = arr.section("A'''", 8, "the varied answer, with fourths and bells; tabor fill",
                    "a last flourish up to C6, then home to D")
    arr.play("recorder", s, A2)
    arr.play("recorder", s, A2, 0.5, double=-3)
    arr.chords("lute", s, A2_CH, ARP, 3, 0.85)
    arr.chords("lutebass", s, A2_CH, BASS, 2)
    arr.drone(s, 8, ["D3", "A3"], 0.7)
    jig(s, 8)
    arr.drums("tamb", s, " | ".join(["J . j J . j"] * 7 + ["W . . . . ."]), 0.8)
    s = arr.section("turnaround", 4, "lute on C then D, drone and tabor alone",
                    "the dance winds down to the drone it started from, and begins again")
    arr.play("recorder", s, "E5 - D5 C5 - A4 | D5 - - - - - | . . . . . . | . . . . . .", 0.8)
    arr.chords("lute", s, "C Dm Dm Dm", "0 2 3 . . .", 3, 0.7)
    arr.chords("lutebass", s, "C Dm", BASS, 2)
    arr.drone(s, 4, ["D3", "A3"], 0.8)
    jig(s, 4, vel=0.8)
    return arr


# ------------------------------------------------------------------ 2. The Filter Keep

def filter_keep() -> Arrangement:
    """D Aeolian, a 4/4 march: proud and armoured. Shawm in fifths over a drone."""
    arr = Arrangement("filter_keep", "The Filter Keep", "D Aeolian", "4/4 march",
                      "quarter = 104", 60 / 104 / 2, 8, 2, scale("D", "aeolian"))
    arr.motif = "D5 . . A4 D5 . F5 | E5 D5 C5 A4 (a dotted call up the D minor chord, then a step down)"
    arr.instruments = {"lead": "shawm, doubled a fifth below from A'' on",
                       "accompaniment": "lute strumming on the beats; lute bass in halves",
                       "bed": "hurdy-gurdy drone on D and A",
                       "percussion": "field drum: bass drum, snare, rolls at every section end",
                       "colour": "bell on the downbeats of the last section"}
    A = ("D5 - - -+A4 D5 - F5 - | E5 - D5 - C5 - A4 - | Bb4 - - -+C5 D5 - Bb4 - | C5 - - - . . . . |"
         "D5 - - -+A4 D5 - F5 - | G5 - F5 - E5 - D5 - | C5 - E5 - G5 - F5+E5 D5+C5 | D5 - - - - - . .")
    A_CH = "Dm Dm Bb C Dm Gm C Dm"
    B = ("F5 - - G5 A5 - F5 - | C6 - A5 - G5 - F5 - | G5 - - A5 Bb5 - G5 - | A5 - - - F5 - . . |"
         "Bb5 - A5 - G5 - F5 - | A5 - G5 - F5 - E5 - | F5 - E5 - D5 - C5 - | D5 - E5 - F5 - E5 -")
    B_CH = "F F Gm F Bb C Dm Am"
    STRUM = "012 . 012 . 012 . 012 ."
    BASS = "0 . . . 2 . . ."
    MARCH = "K . S . K . S s"
    ROLL = "K . S . K . R R"

    def march(bar, bars, vel=1.0, last_roll=True):
        arr.drums("field", bar, " | ".join([MARCH] * (bars - 1) + [ROLL if last_roll else MARCH]),
                  vel)

    s = arr.section("intro", 2, "drone and field drum alone, a roll into the theme",
                    "the gate of a keep: armour clinks, something solemn approaches")
    arr.drone(s, 2, ["D3", "A3"])
    march(s, 2, 0.75)
    s = arr.section("A", 8, "shawm alone states the motif over lute, bass and drum",
                    "a proud call, plain and confident")
    arr.play("shawm", s, A)
    arr.chords("lute", s, A_CH, STRUM, 3, 0.65)
    arr.chords("lutebass", s, A_CH, BASS, 2)
    arr.drone(s, 8, ["D3", "A3"], 0.7)
    march(s, 8)
    s = arr.section("B", 8, "shawm high in F major; lute arpeggios instead of strums",
                    "the banners lift: brighter and higher, ending on a question (A minor)")
    arr.play("shawm", s, B)
    arr.chords("lute", s, B_CH, "0 2 3 2 0 2 3 2", 3, 0.6)
    arr.chords("lutebass", s, B_CH, BASS, 2)
    march(s, 8)
    s = arr.section("bridge", 4, "drone and a low recorder alone; a short roll at the end",
                    "the hall goes quiet before the last charge")
    arr.drone(s, 4, ["D3", "A3"], 0.6)
    arr.play("recorder", s, "D5 - - - C5 - A4 - | Bb4 - A4 - G4 - A4 - |"
                            "D5 - - - E5 - F5 - | E5 - - - - - . .", 0.8)
    arr.drums("field", s, "k . . . . . . . | k . . . . . . . | k . . . k . . . | k . . . s s R R",
              0.5)
    s = arr.section("A''", 8, "fullest: shawm doubled in fifths, strums, bass, drone, "
                    "drum, bells", "the whole garrison marches: heavy, proud, unstoppable")
    arr.play("shawm", s, A)
    arr.play("shawm", s, A, 0.5, double=-4)
    arr.chords("lute", s, A_CH, STRUM, 3, 0.75)
    arr.chords("lutebass", s, A_CH, BASS, 2)
    arr.drone(s, 8, ["D3", "A3"], 0.8)
    march(s, 8)
    arr.play("bell", s, "D6 - - - - - - - | . . . . . . . . | . . . . . . . . | . . . . . . . . |"
                        "A5 - - - - - - - | . . . . . . . . | . . . . . . . . | D6 - - - - - - -",
             0.45)
    return arr


# ------------------------------------------------------------------ 3. Estampie of Sparks

def estampie() -> Arrangement:
    """G Mixolydian, 3/4 with a cadential hemiola: bright, heroic, dancing."""
    arr = Arrangement("estampie", "Estampie of Sparks", "G Mixolydian",
                      "3/4, hemiola in bars 3-4 of every phrase", "quarter = 152",
                      60 / 152 / 2, 6, 2, scale("G", "mixolydian"))
    arr.motif = "G5 B5 D6 | C6 B5 A5 G5 (a leap up the G chord, then a dancing fall)"
    arr.instruments = {"lead": "fiddle (A'' adds a recorder a fifth below)",
                       "accompaniment": "harp arpeggios; lute bass on the hemiola accents",
                       "bed": "hurdy-gurdy drone on G and D",
                       "percussion": "tabor, tambourine on the busy sections",
                       "colour": "bells on the high points"}
    # Bars 3-4 of each phrase are a hemiola: three half notes across two bars of 3/4.
    A = ("G5 - B5 - D6 - | C6 - B5 A5 G5 - | A5 - - - F5 - | - - G5 - - - |"
         "G5 - B5 - D6 - | E6 - D6 C6 B5 - | C6 - - - A5 - | - - G5 - - -")
    A_CH = "G G F F,G G C F G"
    B = ("E5 - F5 - G5 - | C5 - D5 - E5 - | F5 - - - E5 - | - - D5 - - - |"
         "E5 - F5 - G5 - | A5 - G5 - F5 - | E5 - - - C5 - | - - D5 - - -")
    B_CH = "C C F Dm C F Am Dm"
    BRIDGE = ("G4 - - - B4 - | D5 - - - - - | C5 - - - A4 - | G4 - - - - - |"
              "G4 - - - B4 - | D5 - - - E5 - | F5 - - - D5 - | D5 - - - - .")
    ARP = "0 2 3 2 4 2"
    DANCE = "D . t . t ."
    HEMI = "D . . . D . | . . D . . ."          # accents follow the hemiola

    def dance(bar, bars, vel=1.0):
        phrase = " | ".join([DANCE, DANCE, HEMI])
        arr.drums("tabor", bar, " | ".join([phrase] * (bars // 4)), vel)

    def hemi_bass(bar, names):
        arr.chords("lutebass", bar, names, "0 . . . 2 . ", 2)

    s = arr.section("intro", 4, "drone and tabor; harp arpeggios from bar 3",
                    "sparks crackle: a bright courtyard, a dance about to begin")
    arr.drone(s, 4, ["G2", "D3"])
    dance(s, 4, 0.8)
    arr.chords("harp", s + 2, "G F,G", ARP, 3, 0.7)
    s = arr.section("A", 8, "fiddle states the motif over harp and tabor",
                    "a heroic leap and a whirling fall: bright and sure")
    arr.play("fiddle", s, A)
    arr.chords("harp", s, A_CH, ARP, 3, 0.75)
    hemi_bass(s, A_CH)
    arr.drone(s, 8, ["G2", "D3"], 0.6)
    dance(s, 8)
    s = arr.section("A'", 8, "fiddle again; tambourine joins; bells on the peaks",
                    "the dance gathers dancers")
    arr.play("fiddle", s, A)
    arr.chords("harp", s, A_CH, ARP, 3, 0.75)
    hemi_bass(s, A_CH)
    arr.drone(s, 8, ["G2", "D3"], 0.6)
    dance(s, 8)
    arr.drums("tamb", s, " | ".join(["J . j . j ."] * 8), 0.7)
    arr.play("bell", s, "D6 - - - - - | . . . . . . | . . . . . . | . . . . . . |"
                        ". . . . . . | E6 - - - - - | . . . . . . | . . . . . .", 0.45)
    s = arr.section("B", 8, "fiddle lower, in C; harp thins to the beats",
                    "a turn of the dance: warmer and lower, ending open on D")
    arr.play("fiddle", s, B)
    arr.chords("harp", s, B_CH, "0 . 2 . 3 .", 3, 0.7)
    hemi_bass(s, B_CH)
    dance(s, 8, 0.85)
    s = arr.section("bridge", 8, "drone and harp solo (the motif slowed down)",
                    "the dancers catch their breath; the harp hums the tune")
    arr.drone(s, 8, ["G2", "D3"])
    arr.play("harp", s, BRIDGE)
    arr.drums("tabor", s, " | ".join(["d . . . . ."] * 7 + ["D . t t R R"]), 0.6)
    s = arr.section("A''", 8, "fullest: fiddle with a recorder a fifth below, harp, bass, "
                    "drone, tabor, tambourine, bells", "everyone in the ring at once")
    arr.play("fiddle", s, A)
    arr.play("recorder", s, A, 0.45, double=-4)
    arr.chords("harp", s, A_CH, ARP, 3, 0.8)
    hemi_bass(s, A_CH)
    arr.drone(s, 8, ["G2", "D3"], 0.7)
    dance(s, 8)
    arr.drums("tamb", s, " | ".join(["J . j . j ."] * 8), 0.8)
    arr.play("bell", s, "D6 - - - - - | . . . . . . | . . . . . . | G5 - - - - - |"
                        ". . . . . . | E6 - - - - - | . . . . . . | G5 - - - - -", 0.5)
    s = arr.section("B'", 8, "fiddle and harp, tambourine shakes",
                    "the last turn of the dance")
    arr.play("fiddle", s, B)
    arr.chords("harp", s, B_CH, ARP, 3, 0.75)
    hemi_bass(s, B_CH)
    arr.drone(s, 8, ["G2", "D3"], 0.6)
    dance(s, 8)
    arr.drums("tamb", s, " | ".join(["W . . . j ."] * 8), 0.6)
    s = arr.section("turnaround", 4, "a cadential hemiola on fiddle, then drone and tabor",
                    "a bow to the partner, and the dance starts over")
    arr.play("fiddle", s, "G5 - D5 - B4 - | C5 - - - A4 - | - - G4 - - - | . . . . . .", 0.85)
    arr.chords("harp", s, "G F G G", "0 2 3 . . .", 3, 0.7)
    arr.drone(s, 4, ["G2", "D3"], 0.8)
    dance(s, 4, 0.8)
    return arr


# ------------------------------------------------------------------ 4. Lantern over Codd

def lantern() -> Arrangement:
    """E Aeolian, 4/4 at 92 with a half-time drum: wistful but determined. The calm one."""
    arr = Arrangement("lantern", "Lantern over Codd", "E Aeolian", "4/4, half-time drum",
                      "quarter = 92", 60 / 92 / 2, 8, 2, scale("E", "aeolian"))
    arr.motif = "E5 . G5 F#5 | E5 D5 B4 (a lifted third that sinks back, like a held breath)"
    arr.instruments = {"lead": "recorder (soft, singing; A'' adds a second one a fourth below)",
                       "accompaniment": "harp ostinato in eighths",
                       "bed": "hurdy-gurdy drone on E and B",
                       "percussion": "tabor in half time (dum on 1, rim on 3)",
                       "colour": "bells, sparse, in the bridge and the last section"}
    A = ("E5 - - - G5 - F#5 - | E5 - D5 - B4 - - - | C5 - - - E5 - D5 - | B4 - - - - - . . |"
         "E5 - - - G5 - A5 - | B5 - - - A5 - G5 - | F#5 - - - E5 - D5 - | E5 - - - - - - .")
    A_CH = "Em Em C Bm Em G D Em"
    B = ("G5 - - - B5 - A5 - | G5 - - - D5 - - - | C5 - - - E5 - A5 - | F#5 - - - - - D5 -")
    B_CH = "G G C D"
    OST = "0 2 3 4 5 4 3 2"
    HALF = "D . . . t . . ."
    HALF_FULL = "D . . . T . . t"

    s = arr.section("intro", 2, "harp ostinato and drone",
                    "a lantern is lit in the dark: calm, steady, a little sad")
    arr.drone(s, 2, ["E2", "B2"])
    arr.chords("harp", s, "Em C", OST, 3, 0.7)
    s = arr.section("A", 8, "recorder sings the motif; harp; half-time tabor from bar 3",
                    "a quiet resolve: this is worth fighting for")
    arr.play("recorder", s, A)
    arr.chords("harp", s, A_CH, OST, 3, 0.75)
    arr.drone(s, 8, ["E2", "B2"], 0.7)
    arr.drums("tabor", s + 2, " | ".join([HALF] * 6), 0.75)
    s = arr.section("B", 4, "recorder higher in G major; bells on the downbeats",
                    "a glimpse of hope, warmer, ending open on D")
    arr.play("recorder", s, B)
    arr.chords("harp", s, B_CH, OST, 3, 0.75)
    arr.drums("tabor", s, " | ".join([HALF_FULL] * 4), 0.8)
    arr.play("bell", s, "B5 - - - - - - - | . . . . . . . . | E6 - - - - - - - | . . . . . . . .",
             0.4)
    s = arr.section("bridge", 4, "harp and drone alone, a few bells",
                    "stillness: the lantern flickers, then holds")
    arr.drone(s, 4, ["E2", "B2"])
    arr.chords("harp", s, "Em Em C D", OST, 3, 0.65)
    arr.play("bell", s, "E6 - - - - - - - | . . . . B5 - - - | . . . . . . . . | D6 - - - - - - -",
             0.4)
    s = arr.section("A''", 8, "fullest: two recorders in fourths, harp, drone, tabor, bells",
                    "the same resolve, steadier now, and home to E")
    arr.play("recorder", s, A)
    arr.play("recorder", s + 4, A.split("|", 4)[4], 0.5, double=-3)
    arr.chords("harp", s, A_CH, OST, 3, 0.8)
    arr.drone(s, 8, ["E2", "B2"], 0.8)
    arr.drums("tabor", s, " | ".join([HALF_FULL] * 7 + ["D . . . T . R R"]), 0.85)
    arr.play("bell", s, "E6 - - - - - - - | . . . . . . . . | . . . . . . . . | . . . . . . . . |"
                        ". . . . . . . . | . . . . . . . . | . . . . . . . . | B5 - - - - - - -",
             0.35)
    return arr


# ------------------------------------------------------------------ 5. Saltarello of the Spire

def saltarello() -> Arrangement:
    """A Dorian, fast 6/8: two leads in call and response, full percussion. Exhilarating."""
    arr = Arrangement("saltarello", "Saltarello of the Spire", "A Dorian", "6/8",
                      "dotted quarter = 150", 60 / 150 / 3, 6, 3, scale("A", "dorian"))
    arr.motif = "A5 B5 C6 B5 | A5 G5 E5 (the recorder asks), E5 F#5 G5 F#5 | E5 D5 A4 (the shawm answers)"
    arr.instruments = {"lead": "recorder calls, shawm answers; together in fourths at the end",
                       "accompaniment": "harp arpeggios; lute bass",
                       "bed": "hurdy-gurdy drone on A and E",
                       "percussion": "tabor, tambourine, all of it", "colour": "bells on the peaks"}
    CALL1, RESP1 = "A5 - B5 C6 - B5 | A5 - G5 E5 - -", "E5 - F#5 G5 - F#5 | E5 - D5 A4 - -"
    CALL2, RESP2 = "A5 - B5 C6 - D6 | E6 - D6 C6 - B5", "A5 - G5 F#5 - D5 | E5 - - A4 - -"
    REST2 = ". . . . . . | . . . . . ."
    A_CH = "Am G,Em Em D,Am Am G Em,D Em,Am"
    B = ["G5 - A5 B5 - G5", "C6 - B5 A5 - -", "G5 - A5 B5 - G5", "E5 - F#5 G5 - -",
         "A5 - G5 F#5 - E5", "D5 - E5 F#5 - -", "G5 - F#5 E5 - D5", "E5 - - - - ."]
    B_CH = "G C G Em D D Em Em"
    BRIDGE = ("A4 - - E4 - - | A4 - - B4 - - | C5 - - B4 - A4 | G4 - - - - - |"
              "A4 - - E4 - - | C5 - - D5 - - | E5 - - D5 - B4 | A4 - - - - .")
    ARP = "0 2 3 4 3 2"
    BASS = "0 . . 2 . ."
    DRIVE = "D . t D t t"
    FILL = "D t+t t D+t R R"
    REST = ". . . . . ."

    def drive(bar, bars, vel=1.0):
        arr.drums("tabor", bar, " | ".join([DRIVE] * (bars - 1) + [FILL]), vel)

    def call_and_answer(bar, vel=1.0):
        arr.play("recorder", bar, " | ".join([CALL1, REST2, CALL2, REST2]), vel)
        arr.play("shawm", bar, " | ".join([REST2, RESP1, REST2, RESP2]), vel * 0.9)

    def b_section(bar, vel=1.0):
        rec = " | ".join(B[i] if i % 2 == 0 else REST for i in range(8))
        sha = " | ".join(B[i] if i % 2 == 1 else REST for i in range(8))
        arr.play("recorder", bar, rec, vel)
        arr.play("shawm", bar, sha, vel * 0.9)

    s = arr.section("intro", 8, "drone and tabor; harp from bar 3, bass and tambourine "
                    "from bar 5", "the spire's stairs: running steps, quickening pulse")
    arr.drone(s, 8, ["A2", "E3"])
    drive(s, 8, 0.8)
    arr.chords("harp", s + 2, "Am G,Am Am D,Am Em Am", ARP, 3, 0.7)
    arr.chords("lutebass", s + 4, "Am Am Em Am", BASS, 2)
    arr.drums("tamb", s + 4, " | ".join(["j . . j . ."] * 4), 0.6)
    s = arr.section("A", 8, "recorder calls, shawm answers, over harp, bass and tabor",
                    "a chase: two voices daring each other")
    call_and_answer(s)
    arr.chords("harp", s, A_CH, ARP, 3, 0.75)
    arr.chords("lutebass", s, A_CH, BASS, 2)
    arr.drone(s, 8, ["A2", "E3"], 0.6)
    drive(s, 8)
    s = arr.section("A'", 8, "the same, with tambourine", "faster feet, the same dare")
    call_and_answer(s)
    arr.chords("harp", s, A_CH, ARP, 3, 0.75)
    arr.chords("lutebass", s, A_CH, BASS, 2)
    arr.drone(s, 8, ["A2", "E3"], 0.6)
    drive(s, 8)
    arr.drums("tamb", s, " | ".join(["J . j J . j"] * 8), 0.75)
    s = arr.section("B", 8, "the leads trade single bars, in G and D",
                    "the chase turns a corner: quicker exchanges, brighter")
    b_section(s)
    arr.chords("harp", s, B_CH, ARP, 3, 0.75)
    arr.chords("lutebass", s, B_CH, BASS, 2)
    drive(s, 8)
    s = arr.section("B'", 8, "B again with tambourine shakes and the drone",
                    "breathless, ending open on E")
    b_section(s)
    arr.chords("harp", s, B_CH, ARP, 3, 0.75)
    arr.chords("lutebass", s, B_CH, BASS, 2)
    arr.drone(s, 8, ["A2", "E3"], 0.6)
    drive(s, 8)
    arr.drums("tamb", s, " | ".join(["W . . j . ."] * 8), 0.7)
    s = arr.section("bridge", 8, "drone, harp solo (the motif slowed down), a quiet pulse",
                    "a landing on the stairs: one deep breath")
    arr.drone(s, 8, ["A2", "E3"])
    arr.play("harp", s, BRIDGE)
    arr.drums("tabor", s, " | ".join(["d . . d . ."] * 7 + ["D t t D R R"]), 0.6)
    s = arr.section("A''", 8, "call and answer again over everything",
                    "the chase resumes at full speed")
    call_and_answer(s)
    arr.chords("harp", s, A_CH, ARP, 3, 0.8)
    arr.chords("lutebass", s, A_CH, BASS, 2)
    arr.drone(s, 8, ["A2", "E3"], 0.7)
    drive(s, 8)
    arr.drums("tamb", s, " | ".join(["J . j J . j"] * 8), 0.8)
    s = arr.section("B''", 8, "B with bells on the peaks", "almost at the top")
    b_section(s)
    arr.chords("harp", s, B_CH, ARP, 3, 0.8)
    arr.chords("lutebass", s, B_CH, BASS, 2)
    arr.drone(s, 8, ["A2", "E3"], 0.7)
    drive(s, 8)
    arr.drums("tamb", s, " | ".join(["J . j J . j"] * 8), 0.8)
    arr.play("bell", s, "C6 - - - - - | . . . . . . | . . . . . . | . . . . . . |"
                        "A5 - - - - - | . . . . . . | . . . . . . | E6 - - - - -", 0.45)
    s = arr.section("A'''", 8, "fullest: both leads together, the shawm a fourth below; "
                    "everything plays", "the top of the spire: both voices as one")
    both = " | ".join([CALL1, RESP1, CALL2, RESP2])
    arr.play("recorder", s, both)
    arr.play("shawm", s, both, 0.55, double=-3)
    arr.chords("harp", s, A_CH, ARP, 3, 0.85)
    arr.chords("lutebass", s, A_CH, BASS, 2)
    arr.drone(s, 8, ["A2", "E3"], 0.8)
    drive(s, 8)
    arr.drums("tamb", s, " | ".join(["J . j J . j"] * 8), 0.85)
    arr.play("bell", s, "A5 - - - - - | . . . . . . | . . . . . . | . . . . . . |"
                        "E6 - - - - - | . . . . . . | . . . . . . | A5 - - - - -", 0.45)
    s = arr.section("turnaround", 6, "a falling cadence, then harp, drone and tabor wind down",
                    "a leap back down the stairs, and up again")
    arr.play("recorder", s, "E5 - D5 C5 - B4 | A4 - - - - - | . . . . . . | . . . . . . |"
                            ". . . . . . | . . . . . .", 0.85)
    arr.chords("harp", s, "Em Am Am G,Am Am Am", "0 2 3 . 3 .", 3, 0.6)
    arr.chords("lutebass", s, "Em Am Am Am", BASS, 2)
    arr.drone(s, 6, ["A2", "E3"], 0.8)
    drive(s, 6, 0.75)
    return arr


# ------------------------------------------------------------------ danger: Last Candle

def last_candle() -> Arrangement:
    """E Phrygian, slow 4/4: the same world, getting dangerous. Tension from the half step
    E-F and from what is left unsaid, never from loudness or speed."""
    arr = Arrangement("last_candle", "Last Candle", "E Phrygian", "4/4", "quarter = 72",
                      60 / 72 / 2, 8, 2, scale("E", "phrygian"), kind="danger")
    # Here the bed, the bell and the heartbeat carry the piece; the recorder only interjects.
    arr.levels.update({"drone": -4.0, "bell": -5.0, "perc": -3.0, "bass": -6.0})
    arr.motif = "E6 F6 E6 . F6 (the bell circles the half step and never settles)"
    arr.instruments = {"lead": "recorder, low, in fragments that rise by step and break off",
                       "accompaniment": "lute tolling E and F low in the middle bars",
                       "bed": "a trembling hurdy-gurdy drone on E and B",
                       "percussion": "a heartbeat: two soft thumps, then space",
                       "colour": "the bell ostinato on E and F"}
    HEART = "H+h . . . H+h . . ."
    BELL = ("E6 . F6 . . E6 . . | . . F6 . E6 . . . | E6 . F6 . . . E6 . | . F6 . . E6 . . .")

    s = arr.section("embers", 2, "the trembling drone and the heartbeat alone",
                    "the room goes quiet; you can hear your own heart")
    arr.drone(s, 12, ["E2", "B2"], 1.0, inst="gurdy_tremble")
    arr.drums("heart", s, " | ".join([HEART] * 2), 0.8)
    s = arr.section("flicker", 2, "the bell ostinato enters: E and F, circling",
                    "something is wrong, and it will not resolve")
    arr.drums("heart", s, " | ".join([HEART] * 2), 0.85)
    arr.play("bell", s, BELL.rsplit("|", 2)[0], 0.4)
    s = arr.section("fragments", 4, "the recorder tries a phrase, rising, and is cut short",
                    "every attempt breaks off a little higher: nerves")
    arr.drums("heart", s, " | ".join([HEART] * 4), 0.9)
    arr.play("bell", s, BELL, 0.42)
    arr.play("recorder", s, "E4 - - F4 G4 - . . | . . . . . . . . |"
                            "F4 - - G4 A4 - . . | . . . . . . . .", 0.7)
    s = arr.section("closing in", 2, "lute tolls E and F low; the recorder climbs higher",
                    "the walls close in; the texture thickens")
    arr.drums("heart", s, " | ".join([HEART] * 2), 1.0)
    arr.play("bell", s, BELL.rsplit("|", 2)[0], 0.45)
    arr.play("lutebass", s, "E3 - - - F3 - - - | E3 - - - F3 - - -", 0.7)
    arr.play("recorder", s, "G4 - - A4 B4 - C5 . | B4 - - - A4 . . .", 0.75)
    s = arr.section("held breath", 2, "the drone, a last low F, the heartbeat",
                    "the phrase hangs on F, unresolved, and the circle starts again")
    arr.drums("heart", s, " | ".join([HEART] * 2), 0.85)
    arr.play("lutebass", s, "F3 - - - - - - - | . . . . . . . .", 0.55)
    return arr


# ------------------------------------------------------------------ the catalogue

TRACKS = {
    "glade_jig": (glade_jig, "theme_glade_jig.wav"),
    "filter_keep": (filter_keep, "theme_filter_keep.wav"),
    "estampie": (estampie, "theme_estampie.wav"),
    "lantern": (lantern, "theme_lantern.wav"),
    "saltarello": (saltarello, "theme_saltarello.wav"),
    "last_candle": (last_candle, "danger_last_candle.wav"),
}


def sheet(arr: Arrangement) -> str:
    """The track's score sheet, in Markdown (docs/MUSIC.md collects them)."""
    lines = [f"### {arr.title}", "",
             f"{arr.mode}, {arr.metre}, {arr.tempo}. {arr.bars} bars, {arr.seconds:.1f} s. "
             f"File: `{TRACKS[arr.key][1]}`.", "", f"**Motif:** {arr.motif}", "",
             "| Role | Instrument |", "|---|---|"]
    lines += [f"| {role} | {inst} |" for role, inst in arr.instruments.items()]
    lines += ["", "| Bars | Section | Who plays | What the listener should feel |",
              "|---|---|---|---|"]
    for s in arr.sections:
        lines.append(f"| {s.first + 1}-{s.first + s.bars} | {s.name} | {s.roles} | {s.feel} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate SQL Witch's battle music.")
    parser.add_argument("--only", choices=sorted(TRACKS), help="write one track only")
    parser.add_argument("--sheet", action="store_true", help="print the score sheets")
    args = parser.parse_args(argv)
    names = [args.only] if args.only else list(TRACKS)
    if args.sheet:
        for name in names:
            print(sheet(TRACKS[name][0]()))
        return
    total = 0
    print(f"Writing music to {OUT}")
    for name in names:
        build, filename = TRACKS[name]
        arr = build()
        print(f"  {filename}: {arr.title}, {arr.bars} bars")
        size = write(filename, render(arr, report=True))
        total += size
        print(f"    {arr.seconds:5.1f} s  {size / 1e6:4.2f} MB")
    print(f"  total {total / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
