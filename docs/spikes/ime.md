# Spike: Chinese typing and Chinese text in pygame-ce

Question (plan risk table, prompt 01 §5): can the game receive Chinese typed through an input
method editor (IME), and draw Chinese legibly? If not, decision D0 (stay on pygame-ce) reopens.

Tested with pygame-ce 2.5.8 on SDL 2.32.10, Python 3.13, in the cloud build container (Linux,
no display, no IME). Script: `tools/spike_ime.py`.

## Verdict

**Not blocking, but not yet proven on a real IME.** Everything that can be checked without a real
input method passes. D0 stays as it is, with one task for the author (below) before Phase 0 ends.

## What was checked

| Check | Result |
|---|---|
| The event types exist and carry the IME's data | Yes. `TEXTEDITING` has `text` (the draft), `start` (cursor) and `length` (selection); `TEXTINPUT` has the committed `text`. A posted pinyin session (`x` … `xuexi` → `学习`, then commit) arrives in order. |
| Telling SDL where the candidate list goes | `pygame.key.set_text_input_rect(rect)` exists in 2.5.8. |
| Letting the OS draw its candidate window | The `SDL_IME_SHOW_UI=1` hint is set before `pygame.init()`. |
| A font that draws Chinese at the 2x layer size | GNU Unifont (bundled, `assets/fonts/unifont.otf`) loads with `pygame.freetype` at 16 px. It covers **all 20,992 CJK Unified Ideographs** (U+4E00–U+9FFF), so Simplified and Traditional are both covered, plus Greek, Cyrillic and every EU diacritic tried (Polish, Maltese, Irish, Romanian). |
| Mixed scripts in one line | `学习 學習 SELECT` renders in one call. |

## What could not be checked here, and must be on a real machine

The container has no IME. Real composition events depend on the platform:

- **Windows:** the Microsoft Pinyin IME works with SDL 2 out of the box; with
  `SDL_IME_SHOW_UI=1` the candidate list is drawn by Windows next to the input rectangle.
- **macOS:** the system input sources send composition events to SDL windows; the candidate
  window is drawn by macOS.
- **Linux:** SDL needs IBus or Fcitx running; if composition does not arrive, start the game with
  `SDL_IM_MODULE=ibus` (or `fcitx`). Some Wayland sessions need `SDL_VIDEODRIVER=x11`.

**Task for the author (10 minutes, on your PC):** install a Chinese input method, run
`python -m tools.spike_ime`, type `xuexi` and choose 学习. The draft must appear underlined while
you type and turn into the committed text; the log at the bottom shows the raw events. If the
draft never appears but committed text does, composition is not reaching SDL: try the Linux
variables above. If nothing at all arrives, say so: D0 reopens.

## Fonts

- **Unifont** is the fallback for everything (dual-licensed upstream: SIL OFL 1.1, or GPL-2.0+
  with the font embedding exception). It is a 16 px design, which is exactly the 2x layer size.
- **Fusion Pixel Font** and **Zpix** (both SIL OFL 1.1) are prettier pixel fonts for Chinese.
  They could not be downloaded from the build container (GitHub releases are blocked there).
  To use one later: put the file in `assets/fonts/` and list it first in the font chain; no code
  changes (prompt 04's font service reads the chain from data).
- The game's own 5x7 pixel font stays for Latin text; Unifont is only asked for characters it
  lacks (prompt 04).
