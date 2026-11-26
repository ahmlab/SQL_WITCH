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


def pytest_configure(config):
    config.addinivalue_line("markers", "speech_waits: speech boxes wait for ENTER, as in play")


@pytest.fixture(autouse=True)
def _speech_closes_by_itself(request):
    """In play, a battle's speech box waits for ENTER (data/pacing.json). Tests that play
    whole battles by time let it close by itself, unless marked speech_waits."""
    if request.node.get_closest_marker("speech_waits"):
        yield
        return
    try:
        from story.pacing import settings
    except Exception:                       # a test module that never touches the story
        yield
        return
    look = settings()["battle_speech"]
    before = look["wait_for_enter"]
    look["wait_for_enter"] = False
    yield
    look["wait_for_enter"] = before
