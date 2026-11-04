import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import sqlglot

from ai import steering
from ai.base import Intent
from ai.goals import AtomicGoal, CompositeGoal, Context, Evaluator, Status, Think
from ai.knight import KNIGHT_INTENTS, KnightBrain, knight_legal_intents
from ai.perception import WEAKNESS_MEMORY, Perception
from ai.styles import KNIGHT_RUNES, render_knight
from magic import guard, rules
from magic.battle import Battle
from magic.cast import load_state, resolve
from magic.db import build_db
from magic.rules import CastMemory

ROOT = Path(__file__).resolve().parent.parent


def knight_state(**foe):
    conn = build_db(level=2, foe_ids=[2])
    state = load_state(conn, foe_id=2, seed=1)
    state.ada.runes = {"LIMIT", "WHERE"}
    state.foe.runes = set(KNIGHT_RUNES)
    for name, value in foe.items():
        setattr(state.foe, name, value)
    return conn, state


def memory(turn, damage=30, super_effective=True, scry=False):
    return CastMemory(turn, ("WHERE",), ("Storm",), damage, super_effective, 0, scry)


# ------------------------------------------------------------------ perception

def test_perception_sees_both_sides_and_what_it_can_afford():
    _, state = knight_state(mp=5)
    p = Perception({"strike": 4, "heavy": 7}).sense(state)
    assert p.my_mp == 5 and p.ada_hp == 75
    assert p.affordable == {"strike"}
    assert p.can_afford("strike") and not p.can_afford("strike", "heavy")


def test_perception_remembers_damage_and_a_found_weakness_then_forgets_it():
    _, state = knight_state()
    eyes = Perception({"strike": 4})
    assert eyes.sense(state).threat == 0 and eyes.sense(state).weakness_known == 0
    state.ada_casts.append(memory(turn=1, damage=40))
    p = eyes.sense(state)
    assert p.threat > 0 and p.weakness_known == 1.0
    assert "weakness" in eyes.log[0]
    state.turn = 1 + WEAKNESS_MEMORY
    assert eyes.sense(state).weakness_known == 0.0          # out of mind


def test_perception_ignores_scrying_for_threat():
    _, state = knight_state()
    eyes = Perception({})
    state.ada_casts.append(memory(turn=1, damage=0, super_effective=False, scry=True))
    assert eyes.sense(state).threat == 0


# ------------------------------------------------------------------ goals

def test_an_atomic_goal_fails_when_the_percept_forbids_it():
    _, state = knight_state(mp=0)
    ctx = Context(Perception({"strike": 4}).sense(state), random.Random(0))
    goal = AtomicGoal("strike", KNIGHT_INTENTS["strike"], requires=lambda p: p.can("strike"))
    assert goal.step(ctx) is Status.FAILED and ctx.intent is None


def test_a_composite_goal_spans_several_turns():
    _, state = knight_state()
    p = Perception({}).sense(state)
    plan = CompositeGoal("combo", [AtomicGoal("move", movement=steering.Movement("seek")),
                                   AtomicGoal("a", Intent("a")), AtomicGoal("b", Intent("b"))])
    first = Context(p, random.Random(0))
    assert plan.step(first) is Status.ACTIVE and first.intent.action == "a"
    assert first.movement.behaviour == "seek"            # the reposition happened on the way
    second = Context(p, random.Random(0))
    assert plan.step(second) is Status.COMPLETED and second.intent.action == "b"


def make_think(scores, penalty=1.0):
    return Think([Evaluator(name, lambda p, m, v=value: v,
                            lambda p, n=name: AtomicGoal(n, Intent(n))) for name, value in
                  scores.items()], penalty)


def test_think_picks_the_most_desirable_goal():
    _, state = knight_state()
    p = Perception({}).sense(state)
    think = make_think({"low": 0.2, "high": 1.0})
    assert think.think(Context(p, random.Random(0)), "any").action == "high"


def test_think_replans_when_the_best_plan_cannot_act():
    _, state = knight_state(mp=0)
    p = Perception({"strike": 4}).sense(state)
    think = Think([
        Evaluator("strike", lambda p, m: 2.0,
                  lambda p: AtomicGoal("strike", KNIGHT_INTENTS["strike"],
                                       requires=lambda q: q.can("strike"))),
        Evaluator("rest", lambda p, m: 0.1, lambda p: AtomicGoal("rest", KNIGHT_INTENTS["rest"])),
    ])
    ctx = Context(p, random.Random(0))
    assert think.think(ctx, "any").action == "rest"
    assert any("drop strike" in step for step in ctx.trace)


def test_think_keeps_a_plan_it_has_committed_to(monkeypatch):
    monkeypatch.setattr("ai.goals.NOISE", (1.0, 1.0))      # no dice: test the rule itself
    _, state = knight_state()
    p = Perception({}).sense(state)
    scores = {"plan": 1.0, "rival": 0.9}
    think = Think([
        Evaluator("plan", lambda p, m: scores["plan"],
                  lambda p: CompositeGoal("plan", [AtomicGoal("1", Intent("1")),
                                                   AtomicGoal("2", Intent("2"))])),
        Evaluator("rival", lambda p, m: scores["rival"], lambda p: AtomicGoal("r", Intent("r"))),
    ])
    assert think.think(Context(p, random.Random(1)), "any").action == "1"
    scores["rival"] = 1.05                                 # better, but not 25% better
    assert think.think(Context(p, random.Random(1)), "any").action == "2"


def test_repeating_a_plan_gets_less_attractive():
    _, state = knight_state()
    p = Perception({}).sense(state)
    think = make_think({"guard": 1.0, "strike": 0.8}, penalty=0.55)
    picks = [think.think(Context(p, random.Random(i)), "any").action for i in range(6)]
    assert "strike" in picks and "guard" in picks


# ------------------------------------------------------------------ steering

def body(x=0.0, y=0.0):
    return steering.Kinematic(steering.Vec(x, y))


def simulate(order, agent, places, seconds, rng=None):
    rng, state = rng or random.Random(0), steering.WanderState()
    for _ in range(int(seconds * 60)):
        agent.integrate(steering.steer(order, agent, places, state, rng), 1 / 60)
    return agent


def test_seek_and_flee_push_in_opposite_directions():
    agent, target = body(), steering.Vec(10, 0)
    assert steering.seek(agent, target).x > 0
    assert steering.flee(agent, target).x < 0


def test_arrive_stops_on_the_spot():
    places = {"home": body(), "front": body(80, 20)}
    agent = simulate(steering.Movement("arrive", "front"), body(), places, 4)
    assert (agent.position - steering.Vec(80, 20)).length() < 2
    assert agent.velocity.length() < 3


def test_speed_never_exceeds_the_cap():
    places = {"home": body(), "ada": body(-500, 0)}
    agent = simulate(steering.Movement("seek", "ada"), body(), places, 3)
    assert agent.velocity.length() <= agent.max_speed + 1e-6


def test_pursue_aims_ahead_of_a_moving_target():
    agent = body()
    target = steering.Kinematic(steering.Vec(50, 0), steering.Vec(0, 40))
    assert steering.pursue(agent, target).y > 0              # leads towards where it goes


def test_wander_prowls_near_home():
    places = {"home": body(100, 50)}
    agent = simulate(steering.Movement("wander", "home"), body(100, 50), places, 10)
    assert (agent.position - steering.Vec(100, 50)).length() < 30


# ------------------------------------------------------------------ Sir Wherewell's rules

def test_the_ward_of_relevance_deflects_what_is_not_super_effective():
    conn, state = knight_state(relevance=True)
    report = resolve(conn, state, "SELECT name FROM spells WHERE name = 'Ember'", "ada",
                     random.Random(0))
    assert report.casts[0].deflected and report.casts[0].damage == 0
    assert state.foe.hp == state.foe.max_hp and state.foe.relevance
    assert ("deflect", 0, "Ember", "Sir Wherewell") in report.events


def test_a_super_effective_spell_lands_and_shatters_the_ward():
    conn, state = knight_state(relevance=True)
    report = resolve(conn, state, "SELECT name FROM spells WHERE name = 'Spark'", "ada",
                     random.Random(0))
    assert report.casts[0].damage > 0 and not state.foe.relevance
    assert ("shatter", "Sir Wherewell") in report.events


def test_his_spells_raise_the_ward_and_dispel_adas():
    conn, state = knight_state()
    resolve(conn, state, render_knight(KNIGHT_INTENTS["relevance"], state, 1), "foe",
            random.Random(0))
    assert state.foe.relevance
    state.ada.ward = 20
    resolve(conn, state, render_knight(KNIGHT_INTENTS["dispel"], state, 2), "foe",
            random.Random(0))
    assert state.ada.ward == 0


@pytest.mark.parametrize("action", sorted(KNIGHT_INTENTS))
def test_every_knight_query_is_precise_and_passes_the_rune_gate(action):
    conn, state = knight_state()
    sql = render_knight(KNIGHT_INTENTS[action], state, 1)
    assert "WHERE" in guard.inspect(sql, KNIGHT_RUNES)
    report = resolve(conn, state, sql, "foe", random.Random(0))
    assert len(report.rows) == 1                           # exactly one row: never overflows
    assert report.scry == (action == "rest")


@pytest.mark.parametrize("action", ["strike", "heavy", "finisher", "relevance", "guard"])
def test_mutation_an_empty_filter_makes_the_knight_do_nothing(action):
    conn, state = knight_state()
    sql = render_knight(KNIGHT_INTENTS[action], state, 1)
    broken = sqlglot.parse_one(sql, read="sqlite").where("1 = 0").sql(dialect="sqlite")
    report = resolve(conn, state, broken, "foe", random.Random(0))
    assert report.rows == [] and (state.ada.hp, state.foe.mp) == (75, 40)


def test_he_never_asks_for_a_spell_he_cannot_pay_for():
    conn, state = knight_state(mp=5)
    sql = render_knight(KNIGHT_INTENTS["finisher"], state, 1)        # costs 12
    assert "mp_cost <= 5" in sql
    assert resolve(conn, state, sql, "foe", random.Random(0)).rows == []


# ------------------------------------------------------------------ Sir Wherewell's brain

def decide(brain, state, seed=0):
    return brain.decide(state, random.Random(seed)).action


@pytest.mark.parametrize("seed", range(20))
def test_he_opens_by_raising_his_ward(seed):
    _, state = knight_state()
    assert decide(KnightBrain(), state, seed) == "relevance"


def test_finding_his_weakness_makes_him_besieged():
    _, state = knight_state(relevance=True)
    brain = KnightBrain()
    state.ada_casts.append(memory(turn=1))
    brain.decide(state, random.Random(0))
    assert brain.mode == "besieged"


def test_low_hp_makes_him_desperate_and_he_finishes_a_weak_ada():
    _, state = knight_state(relevance=True, hp=40)
    state.ada.hp = 20
    brain = KnightBrain()
    assert decide(brain, state) == "finisher" and brain.mode == "desperate"
    assert brain.movement == steering.Movement("pursue", "ada")


def test_without_mp_he_catches_his_breath():
    _, state = knight_state(relevance=True, mp=2)
    brain = KnightBrain()
    assert decide(brain, state) == "rest" and brain.mode == "winded"


def test_he_strips_a_thick_ward():
    _, state = knight_state(relevance=True)
    state.ada.ward = 30
    actions = Counter(decide(KnightBrain(), state, seed) for seed in range(30))
    assert actions["dispel"] > 15


@pytest.mark.parametrize("seed", range(10))
def test_the_knight_only_returns_legal_intents(seed):
    _, state = knight_state()
    brain, rng = KnightBrain(), random.Random(seed)
    legal = knight_legal_intents(state)
    for _ in range(25):
        state.foe.hp = rng.randint(1, state.foe.max_hp)
        state.foe.mp = rng.randint(0, state.foe.max_mp)
        state.foe.relevance = rng.random() < 0.5
        state.ada.hp = rng.randint(1, state.ada.max_hp)
        state.ada.ward = rng.choice([0, 0, 12, 30])
        assert brain.decide(state, rng) in legal


def test_explain_names_every_technique():
    _, state = knight_state()
    brain = KnightBrain()
    brain.decide(state, random.Random(0))
    why = brain.explain()
    assert {"mode", "sees", "noticed", "goals", "plan", "intent", "movement"} <= set(why)
    assert "restore_ward" in why["goals"] and why["movement"] == "arrive home"


# ------------------------------------------------------------------ the battle

def test_his_first_query_teaches_where():
    battle = Battle(seed=1, guardian="knight")
    assert battle.state.ada.runes == {"LIMIT"} and battle.whose_turn == "foe"
    turn = battle.foe_act()
    assert turn.invitation == "WHERE" and "WHERE" in battle.state.ada.runes
    assert battle.state.foe.relevance


def test_only_the_guardian_of_the_battle_is_in_the_world():
    battle = Battle(seed=1, guardian="knight")
    assert battle.conn.execute("SELECT name FROM enemies").fetchall() == [("Sir Wherewell",)]
    assert {r[0] for r in battle.conn.execute("SELECT DISTINCT foe_id FROM foe_spells")} == {2}


def fight(guardian, bot, seed):
    battle = Battle(seed=seed, guardian=guardian)
    for _ in range(300):
        if battle.whose_turn == "over":
            break
        if battle.whose_turn == "ada":
            battle.ada_cast(bot(battle))
        else:
            battle.foe_act()
    return battle


def novice(battle):
    return "SELECT name FROM spells LIMIT 1"                    # Ember: bounces off forever


def expert(battle):
    ada = battle.state.ada
    if ada.hp_ratio < 0.4 and ada.mp >= 7:
        return "SELECT name FROM spells WHERE kind = 'heal' AND element = 'Storm'"
    if ada.mp >= 8:
        return "SELECT name FROM spells WHERE element = 'Storm' AND power > 30 LIMIT 1"
    return "SELECT name FROM spells WHERE element = 'Storm' AND power < 20 LIMIT 1"


def test_the_knight_beats_a_player_who_never_filters_and_loses_to_one_who_does():
    assert all(fight("knight", novice, seed).winner == "foe" for seed in range(8))
    assert all(fight("knight", expert, seed).winner == "ada" for seed in range(8))


def test_the_same_seed_replays_the_same_knight_battle():
    def log(seed):
        battle = fight("knight", expert, seed)
        return battle.conn.execute("SELECT turn, caster, sql FROM query_log").fetchall()
    assert log(3) == log(3)
    assert len({tuple(log(seed)) for seed in range(8)}) > 1


def test_the_terminal_can_fight_the_knight():
    code = ("import sim.play_cli as c; lines = iter(['SELECT * FROM enemies', ':why', ':quit']);"
            "c.main(['--seed', '2', '--foe', 'knight'], read=lambda p: next(lines), out=print)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                         text=True).stdout
    assert "Filter Keep" in out and "WHERE unlocked" in out and "goals:" in out


# ------------------------------------------------------------------ the Slime on the same framework

from ai.fsm import SlimeBrain


def slime_state():
    conn = build_db(level=1, foe_ids=[1])
    return load_state(conn, foe_id=1, seed=1)


def test_the_slime_pounces_when_it_perceives_ada_exhausted():
    state = slime_state()
    state.ada.exhausted = True
    picks = Counter(SlimeBrain(start="wobble").decide(state, random.Random(s)).action
                    for s in range(40))
    assert picks["overcast"] == 40                          # normally only 70% of the time


def test_the_slime_cannot_splat_without_mp_and_replans():
    state = slime_state()
    state.foe.mp = 0
    brain = SlimeBrain()                                    # its opening wants a splat
    assert brain.decide(state, random.Random(0)).action != "overcast"
    assert "drop splat" in brain.explain()["steps"]


def test_the_slime_lunges_to_splat_and_wobbles_while_it_waits():
    state = slime_state()
    brain = SlimeBrain()
    brain.decide(state, random.Random(0))
    assert brain.movement == steering.Movement("seek", "front")
    assert brain.idle_movement() == steering.Movement("arrive", "home")  # back to its puddle


# ------------------------------------------------------------------ the window

def test_a_knight_battle_plays_to_its_result_screen_and_he_walks_around():
    pygame = pytest.importorskip("pygame")
    pygame.init()
    pygame.display.set_mode((320, 180))
    from engine.scenes import BattleScene, Game, ResultScene
    game = Game(pygame.Surface((320, 180)), seed=3, start="knight")
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
    scene = game.scene
    assert isinstance(scene, BattleScene) and scene.key == "knight"
    xs = set()
    for _ in range(60 * 150):
        game.update(16)
        if not isinstance(game.scene, BattleScene):
            break
        xs.add(round(scene.body.position.x))
        if scene.phase == "input":
            for char in expert(scene.battle):
                game.handle(pygame.event.Event(pygame.TEXTINPUT, text=char))
            game.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN,
                                           mod=pygame.KMOD_LCTRL))
    game.update(16)
    assert isinstance(game.scene, ResultScene) and game.scene.won
    assert max(xs) - min(xs) > 40                           # he charged and fell back
