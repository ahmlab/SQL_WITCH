"""SQL Witch: python main.py [--seed N] [--scale K]

Boots pygame, opens the window and runs the scenes with a fixed 60 Hz timestep: the game
always advances in steps of 1/60 s, however fast or slow the machine draws, so animations
and timings are the same everywhere. Rules and brains never see the clock.

STATUS: step 7 done - arguments, fixed timestep, scene manager, clean shutdown.
"""

from __future__ import annotations

import argparse
import os
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402  (the environment variable must be set first)

from engine import render  # noqa: E402
from engine.audio import Audio, init_mixer  # noqa: E402
from engine.scenes import Game  # noqa: E402

UPDATES_PER_SECOND = 60
MAX_CATCH_UP_MS = 250        # after a long stall (window dragged...), do not fast-forward


def step_ms(update: int) -> int:
    """Milliseconds for the update with this index: 16 or 17, adding up to exactly 1000 per
    second, because the scenes keep time in whole milliseconds."""
    return (update + 1) * 1000 // UPDATES_PER_SECOND - update * 1000 // UPDATES_PER_SECOND


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQL Witch: a turn-based RPG where your "
                                                 "queries are spells.")
    parser.add_argument("--seed", type=int, default=None,
                        help="battle seed; the same seed replays the same battle "
                             "(default: from the clock)")
    parser.add_argument("--scale", type=int, default=None,
                        help="window size as a multiple of 320x180 (default: largest that fits)")
    parser.add_argument("--frames", type=int, default=None, help=argparse.SUPPRESS)  # smoke tests
    return parser.parse_args(argv)


def run(seed: int, scale: int | None = None, max_frames: int | None = None) -> int:
    init_mixer()                                   # before pygame.init(): low-latency sound
    pygame.init()
    try:
        screen = render.Screen(scale=scale)
        game = Game(screen.canvas, seed, screen=screen, audio=Audio())
        clock = pygame.time.Clock()
        updates, lag_ms, last = 0, 0.0, time.perf_counter()
        frames = 0
        while game.running:
            now = time.perf_counter()
            lag_ms += min((now - last) * 1000, MAX_CATCH_UP_MS)
            last = now
            for event in pygame.event.get():
                game.handle(event)
            while lag_ms >= step_ms(updates) and game.running:   # fixed timestep
                lag_ms -= step_ms(updates)
                game.update(step_ms(updates))
                updates += 1
            game.draw()
            screen.present(game.vfx)
            clock.tick(UPDATES_PER_SECOND)
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
    except KeyboardInterrupt:
        pass                                   # Ctrl+C in the terminal: leave quietly
    finally:
        pygame.quit()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seed = args.seed if args.seed is not None else int(time.time())
    print(f"SQL Witch - seed {seed} (replay this battle with --seed {seed})")
    return run(seed, args.scale, args.frames)


if __name__ == "__main__":
    raise SystemExit(main())
