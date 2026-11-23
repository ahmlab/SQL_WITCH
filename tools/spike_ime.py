"""Spike (throwaway): can pygame-ce receive Chinese typed through an IME, and draw it?

    python -m tools.spike_ime              # a window: type with your Chinese IME, ESC quits
    python -m tools.spike_ime --synthetic  # no window needed: posts fake IME events, prints

The window shows, live:
- the composition the IME is building (TEXTEDITING: text, cursor start, selection length),
  underlined, at the text-input rectangle (the IME's candidate list should appear next to it);
- the committed text (TEXTINPUT), rendered with GNU Unifont at 16 px, the size the 2x text
  layer (decision D9) would use;
- a log of the raw events, so the findings in docs/spikes/ime.md can be checked on any machine.

Findings: docs/spikes/ime.md. This file is not part of the game.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# Let the operating system draw its own candidate window (SDL 2 hides it on some platforms).
os.environ.setdefault("SDL_IME_SHOW_UI", "1")

import pygame  # noqa: E402
import pygame.freetype  # noqa: E402

FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "unifont.otf"
SIZE = (640, 360)                      # the 2x text layer of decision D9


def describe(event: pygame.event.Event) -> str:
    if event.type == pygame.TEXTEDITING:
        return f"TEXTEDITING text={event.text!r} start={event.start} length={event.length}"
    if event.type == pygame.TEXTINPUT:
        return f"TEXTINPUT   text={event.text!r}"
    return pygame.event.event_name(event.type)


def synthetic() -> list[str]:
    """Post what a pinyin IME sends while typing 'xuexi' and choosing 学习, and read it back."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))
    pygame.key.start_text_input()
    composing = ["x", "xu", "xue", "xuex", "xuexi", "学习"]
    for text in composing:
        pygame.event.post(pygame.event.Event(pygame.TEXTEDITING, text=text, start=len(text),
                                             length=0))
    pygame.event.post(pygame.event.Event(pygame.TEXTEDITING, text="", start=0, length=0))
    pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text="学习"))
    log = [describe(e) for e in pygame.event.get((pygame.TEXTEDITING, pygame.TEXTINPUT))]
    font = pygame.freetype.Font(str(FONT), 16)
    missing = [c for c, m in zip("学习學習", font.get_metrics("学习學習")) if m is None]
    surface, rect = font.render("学习 學習 SELECT", (255, 255, 255))
    log.append(f"rendered {rect.size} px, glyphs missing: {missing or 'none'}")
    pygame.quit()
    return log


def window() -> None:
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    pygame.display.set_caption("IME spike: type with a Chinese input method, ESC quits")
    font = pygame.freetype.Font(str(FONT), 16)
    pygame.key.start_text_input()
    field = pygame.Rect(20, 60, 600, 24)
    pygame.key.set_text_input_rect(field)          # where the IME puts its candidate list
    committed, composition, cursor, log = "", "", 0, []
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN
                                             and event.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE and not composition:
                committed = committed[:-1]
            if event.type == pygame.TEXTEDITING:
                composition, cursor = event.text, event.start
            if event.type == pygame.TEXTINPUT:
                committed += event.text
                composition = ""
            if event.type in (pygame.TEXTEDITING, pygame.TEXTINPUT):
                log = (log + [describe(event)])[-12:]
                print(describe(event))
        screen.fill((26, 20, 35))
        font.render_to(screen, (20, 20), "Type in Chinese. Committed text:", (198, 166, 240))
        pygame.draw.rect(screen, (246, 236, 208), field)
        x = field.x + 4
        rect = font.render_to(screen, (x, field.y + 4), committed, (26, 20, 35))
        x += rect.width
        if composition:                                  # the IME's draft, underlined
            draft = font.render_to(screen, (x, field.y + 4), composition, (91, 67, 136))
            pygame.draw.line(screen, (91, 67, 136), (x, field.bottom - 3),
                             (x + draft.width, field.bottom - 3))
        for i, line in enumerate(log):
            font.render_to(screen, (20, 110 + i * 18), line, (170, 230, 150))
        pygame.display.flip()
        clock.tick(60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chinese IME spike for pygame-ce.")
    parser.add_argument("--synthetic", action="store_true",
                        help="post fake IME events instead of opening a window")
    args = parser.parse_args(argv)
    if args.synthetic:
        for line in synthetic():
            print(line)
        return 0
    window()
    return 0


if __name__ == "__main__":
    sys.exit(main())
