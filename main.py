"""SQL Witch: python main.py [--seed N] [--scale K] [--start tutorial|slime|knight] [--locale L]
[--save-dir DIR] [--skip-creator] [--smoke-test]

Boots pygame, opens the window and runs the scenes with a fixed 60 Hz timestep: the game
always advances in steps of 1/60 s, however fast or slow the machine draws, so animations
and timings are the same everywhere. Rules and brains never see the clock.

--smoke-test starts the game, draws the title for a moment and quits with exit code 0: CI and
the packaged bundle use it to prove the game really starts on a machine.

STATUS: arguments, fixed timestep, scene manager, clean shutdown, smoke test.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

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
    parser.add_argument("--start", choices=["tutorial", "slime", "knight"], default="tutorial",
                        help="where the story starts: the tutorial, or straight at a guardian "
                             "(default: tutorial)")
    parser.add_argument("--locale", default=None,
                        help="language, e.g. es, zh-Hans, zh-Hant; qps is the pseudo-locale "
                             "for testing (default: English)")
    parser.add_argument("--save-dir", default=None,
                        help="where profiles, saves and settings live (default: the user data "
                             "folder of this OS)")
    parser.add_argument("--skip-creator", action="store_true",
                        help="new games skip the character creator (tests)")
    parser.add_argument("--frames", type=int, default=None, help=argparse.SUPPRESS)  # smoke tests
    parser.add_argument("--smoke-test", action="store_true",
                        help="start, show the title, quit (for CI and packaged builds)")
    return parser.parse_args(argv)


def run(seed: int, scale: int | None = None, max_frames: int | None = None,
        start: str = "tutorial", save_dir: str | None = None, skip_creator: bool = False,
        locale: str | None = None) -> int:
    from save.files import read_json
    from save.profiles import SaveSystem
    from save.settings_file import SettingsFile
    from save.telemetry import https_sender
    init_mixer()                                   # before pygame.init(): low-latency sound
    pygame.init()
    saves = SaveSystem(save_dir)
    settings = SettingsFile(saves.root).load()
    game = None
    try:
        screen = render.Screen(scale=scale or settings.scale, display=settings.display,
                               fill=settings.fill)
        game = Game(screen.canvas, seed, screen=screen, audio=Audio(), start=start,
                    saves=saves, settings=settings, skip_creator=skip_creator, locale=locale)
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
        if game is not None and game.telemetry is not None:   # only with consent, if anywhere
            config, _ = read_json(Path(__file__).parent / "data" / "telemetry.json")
            game.telemetry.flush(https_sender((config or {}).get("endpoint")))
        pygame.quit()
    return 0


SMOKE_FRAMES = 30            # half a second of title screen


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.locale:
        from i18n import CATALOG, set_locale
        if args.locale not in CATALOG.settings()["locales"]:
            print(f"unknown locale {args.locale!r}; see data/i18n/locales.json")
            return 2
        set_locale(args.locale)
    if args.smoke_test:
        import tempfile
        with tempfile.TemporaryDirectory() as folder:      # never touch the player's saves
            code = run(seed=1, scale=1, max_frames=SMOKE_FRAMES, start=args.start,
                       save_dir=args.save_dir or folder, locale=args.locale)
        print("smoke test: the title was shown and the game quit cleanly")
        return code
    seed = args.seed if args.seed is not None else int(time.time())
    print(f"SQL Witch - seed {seed} (replay this battle with --seed {seed})")
    return run(seed, args.scale, args.frames, args.start, args.save_dir, args.skip_creator,
               args.locale)


if __name__ == "__main__":
    raise SystemExit(main())
