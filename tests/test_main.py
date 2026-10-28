import pytest

pygame = pytest.importorskip("pygame")

import main


def test_sixty_updates_make_exactly_one_second():
    steps = [main.step_ms(i) for i in range(60)]
    assert sum(steps) == 1000
    assert set(steps) <= {16, 17}


def test_arguments():
    args = main.parse_args(["--seed", "5", "--scale", "3"])
    assert (args.seed, args.scale) == (5, 3)
    assert main.parse_args([]).seed is None


def test_the_game_boots_runs_and_shuts_down_cleanly():
    assert main.run(seed=1, scale=1, max_frames=10) == 0
    assert not pygame.get_init()
