import os

# Engine tests run without a screen or a sound card (CI, cloud containers).
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pytest  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", help="also run the slow tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="slow: run with --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
