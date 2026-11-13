"""Ada's animation (engine/ada_anim.py): her one sprite, moved row by row."""

import pytest

from engine.ada_anim import (BREATH_FAST_MS, BREATH_MS, CAST_MS, FAINT_MS, HEAD, HIT_MS, ROWS,
                             TYPING_MS, AdaAnimator)


def at(ms, **events):
    a = AdaAnimator()
    a.t = ms
    return a


def head_dy(pose):
    return pose[HEAD[0]][1]


def test_every_pose_has_one_offset_per_row_and_stays_small():
    a = AdaAnimator()
    for t in range(0, 6000, 37):
        a.t = t
        pose = a.pose()
        assert len(pose) == ROWS
        assert all(abs(dx) <= 2 and -1 <= dy <= 2 for dx, dy in pose)
        assert pose[-1] == (0, 0)                             # the feet never move


def test_she_breathes_and_faster_when_her_hp_is_red():
    def breaths(a, ms):
        changes, last = 0, None
        for t in range(0, ms, 20):
            a.t = t
            now = a.pose()[27][1]                             # the shoulders rise and fall
            changes += last is not None and now != last
            last = now
        return changes // 2

    calm, hurt = AdaAnimator(), AdaAnimator()
    hurt.set_low(True)
    assert breaths(calm, 12000) == pytest.approx(12000 / BREATH_MS, abs=1)
    assert breaths(hurt, 12000) == pytest.approx(12000 / BREATH_FAST_MS, abs=1)


def test_hurt_she_hunches():
    a = AdaAnimator()
    a.t = BREATH_MS * 0.9                                     # between breaths
    upright = head_dy(a.pose())
    a.set_low(True)
    assert head_dy(a.pose()) > upright


def test_typing_bows_her_head_and_stopping_lifts_it():
    a = AdaAnimator()
    a.t = BREATH_MS // 2                                     # breathing in: room for TYPING_MS
    upright = head_dy(a.pose())
    a.typed()
    assert head_dy(a.pose()) == upright + 1
    a.update(TYPING_MS)
    assert head_dy(a.pose()) == upright


def test_casting_steps_towards_the_foe_with_glowing_hands_then_back():
    a = AdaAnimator()
    a.t = 1000
    a.cast((209, 75, 75))
    a.update(CAST_MS // 2)
    assert a.pose()[10][0] > 0 and a.glows()
    assert all(colour == (209, 75, 75) for _, _, colour, _ in a.glows())
    a.update(CAST_MS)
    assert all(dx == 0 for dx, _ in a.pose()[6:32]) and not a.glows()


def test_a_hit_throws_her_back_and_shakes_her():
    a = AdaAnimator()
    a.t = 1000
    a.hit()
    a.update(40)
    assert a.pose()[20][0] < 0
    seen = set()
    for _ in range(HIT_MS // 25):
        a.update(25)
        seen.add(a.pose()[20][0])
    assert {-1, 1} <= seen
    a.update(HIT_MS)
    assert a.pose()[20][0] == 0


def test_fainting_folds_her_down_then_over_and_she_stays_down():
    a = AdaAnimator()
    a.faint()
    a.update(FAINT_MS // 2)
    kneeling = a.pose()
    assert kneeling[0][1] > 6 and kneeling[0][0] == 0         # down to her knees first
    a.update(FAINT_MS)
    fallen = a.pose()
    assert fallen[0][1] > kneeling[0][1] and fallen[0][0] < -5   # then over to the left
    a.update(10_000)
    assert a.pose() == fallen and not a.glows()
    a.faint()                                                # asking again changes nothing
    assert a.pose() == fallen


def test_nothing_random_the_same_time_gives_the_same_pose():
    a, b = AdaAnimator(), AdaAnimator()
    for t in (0, 777, 4321):
        a.t = b.t = t
        assert a.pose() == b.pose()


# ------------------------------------------------------------------ in the game

pygame = pytest.importorskip("pygame")


@pytest.fixture(scope="module")
def pygame_up():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield
    pygame.quit()


def test_the_battle_feeds_her_animation(pygame_up):
    from engine import render
    from engine.scenes import BattleScene, Game
    from engine.audio import Silent
    game = Game(pygame.Surface((320, 180)), seed=2, audio=Silent())
    scene = BattleScene(game, "slime")
    game.switch(scene)
    for _ in range(2000):                                    # the Slime opens: Ada is hit
        if scene.phase == "input":
            break
        game.update(16)
    assert scene.ada.hit_at > -10 ** 6
    for char in "SELECT name FROM spells":
        game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))
    assert scene.ada.t - scene.ada.last_key < TYPING_MS
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=pygame.KMOD_LCTRL))
    assert scene.ada.cast_colour is not None
    ada = scene.battle.state.ada
    ada.hp = 0
    scene.shown["ada"][0] = 0
    scene.bars["ada"][0] = 0.0
    scene._update_ada(16)
    assert scene.ada.fainting
    canvas = render.Canvas()
    scene.draw(canvas)                                       # draws without trouble


def test_her_pixels_are_all_drawn_when_standing(pygame_up):
    from engine.ada_anim import AdaAnimator
    from engine.sprites import draw_ada, sprite
    plain, animated = pygame.Surface((40, 60), pygame.SRCALPHA), pygame.Surface((40, 60),
                                                                               pygame.SRCALPHA)
    standing = AdaAnimator()
    standing.t = BREATH_MS // 2                              # between breaths, nothing sways
    draw_ada(plain, (20, 55))
    draw_ada(animated, (20, 55), anim=standing)
    count = lambda s: sum(s.get_at((x, y)).a > 0 for x in range(40) for y in range(60))
    assert count(animated) == count(plain) == pygame.mask.from_surface(sprite("ada_back")).count()
