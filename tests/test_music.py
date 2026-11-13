"""The battle music (tools/make_music.py) and the files it wrote."""

import hashlib
import json
import math
import struct
import wave

import pytest

from tools import make_music
from tools.make_music import FORBIDDEN, TRACKS, parse, render, to_bytes

AUDIO = make_music.OUT
BATTLE = [name for name, (build, _) in TRACKS.items() if build().kind == "battle"]


def samples(filename):
    with wave.open(str(AUDIO / filename)) as w:
        assert (w.getnchannels(), w.getsampwidth()) == (1, 2)
        n = w.getnframes()
        return struct.unpack(f"<{n}h", w.readframes(n)), w.getframerate()


def music_files():
    with open(AUDIO / "sounds.json", encoding="utf-8") as f:
        music = json.load(f)["music"]
    files = set()
    for entry in music.values():
        files |= set(entry.get("files", [entry.get("file")]))
    return sorted(files)


@pytest.fixture(scope="module")
def loaded():
    return {name: samples(filename) for name, (_, filename) in TRACKS.items()}


# ------------------------------------------------------------------ every music file

@pytest.mark.parametrize("filename", music_files())
def test_every_music_file_loops_cleanly_without_clipping_or_dc(filename):
    x, rate = samples(filename)
    assert len(x) > rate
    assert max(abs(v) for v in x) < 32767                   # nothing clipped
    assert abs(sum(x) / len(x)) < 100                       # no DC offset (0.3% of full scale)
    # The seam: the jump from the last sample back to the first is no bigger than the
    # steps the music already makes around it (a click would be far bigger).
    near = x[-200:] + x[:200]
    typical = max(abs(near[i + 1] - near[i]) for i in range(len(near) - 1) if i != 199)
    assert abs(x[0] - x[-1]) <= max(200, typical)


# ------------------------------------------------------------------ the new tracks

def test_battle_themes_last_60_to_80_seconds_and_the_danger_theme_30_to_45(loaded):
    for name, (x, rate) in loaded.items():
        seconds = len(x) / rate
        if name in BATTLE:
            assert 60 <= seconds <= 80, name
        else:
            assert 30 <= seconds <= 45, name


def test_battle_themes_are_within_2_db_of_each_other(loaded):
    level = {name: 20 * math.log10(math.sqrt(sum(v * v for v in x) / len(x)) / 32768)
             for name, (x, _) in loaded.items() if name in BATTLE}
    assert max(level.values()) - min(level.values()) <= 2.0, level


def test_each_track_is_at_most_about_3_mb_and_all_together_under_20():
    sizes = {name: (AUDIO / filename).stat().st_size for name, (_, filename) in TRACKS.items()}
    assert all(size < 3.2e6 for size in sizes.values()), sizes
    everything = sum((AUDIO / f).stat().st_size for f in music_files())
    assert everything < 20e6


@pytest.mark.parametrize("name", sorted(TRACKS))
def test_no_track_plays_a_pitch_that_clashes_with_the_typing_notes(name):
    arrangement = TRACKS[name][0]()
    assert {p % 12 for p in arrangement.pitches()} & FORBIDDEN == set()


def test_there_are_five_battle_themes_and_one_danger_theme():
    assert len(BATTLE) == 5
    assert [n for n in TRACKS if n not in BATTLE] == ["last_candle"]


@pytest.mark.parametrize("name", sorted(TRACKS))
def test_every_track_has_sections_that_cover_it_and_a_score_sheet(name):
    arr = TRACKS[name][0]()
    covered = [bar for s in arr.sections for bar in range(s.first, s.first + s.bars)]
    assert covered == list(range(arr.bars))
    sheet = make_music.sheet(arr)
    assert arr.title in sheet and arr.motif and all(s.feel in sheet for s in arr.sections)


def test_voices_enter_and_drop_out_so_sections_differ_in_loudness(loaded):
    for name in BATTLE:
        x, rate = loaded[name]
        arr = TRACKS[name][0]()
        bar = arr.slots * arr.eighth * rate

        def level(section):
            seg = x[int(section.first * bar):int((section.first + section.bars) * bar)]
            return 10 * math.log10(sum(v * v for v in seg) / len(seg) + 1)

        by_name = {s.name: level(s) for s in arr.sections}
        assert by_name["bridge"] < min(v for k, v in by_name.items()
                                       if k not in ("bridge", "intro", "turnaround")) - 2, name


# ------------------------------------------------------------------ the score language

def test_scores_read_holds_rests_sixteenths_and_grace_notes():
    events, bars = parse("D5 - . E5+F5 G5>F5 -", 6)
    assert bars == 1
    starts = [(e[0], e[1], e[2]) for e in events]
    assert starts[0] == (0, 2, 74)                          # D5 held for two eighths
    assert starts[1] == (3, 0.5, 76) and starts[2] == (3.5, 0.5, 77)
    assert events[3][3] and events[4][2] == 77 and events[4][1] > 1   # grace, then F5 held


def test_a_bar_with_the_wrong_number_of_slots_is_refused():
    with pytest.raises(ValueError, match="bar 2"):
        parse("D5 - - - - - | D5 - -", 6)


# ------------------------------------------------------------------ deterministic

def _fresh_render(bars):
    make_music.render_note.cache_clear()
    make_music.render_hit.cache_clear()
    make_music.instrument_gain.cache_clear()
    return hashlib.sha256(to_bytes(render(make_music.glade_jig(), bars=bars))).hexdigest()


def test_rendering_is_deterministic():
    assert _fresh_render(2) == _fresh_render(2)


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(TRACKS))
def test_the_files_on_disk_are_what_the_generator_writes(name):
    build, filename = TRACKS[name]
    rendered = to_bytes(render(build()))
    with wave.open(str(AUDIO / filename)) as w:
        assert w.readframes(w.getnframes()) == rendered
