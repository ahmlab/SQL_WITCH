# SQL Witch: how the guardians think

Every guardian runs the same loop each turn (`ai/guardian.py`):

```
perceive  ->  change mode (match/case)  ->  Think: pick a goal, run its plan  ->  Intent + Movement
                                                                                   |        |
                                         ai/styles.py writes the Intent as SQL  <--+        +--> steering on screen
                                         (the Intent is then thrown away; only the executed query can hurt anyone)
```

No machine learning is used anywhere. Every decision is a hand-written rule, the only
randomness comes from the battle's seeded `random.Random`, and `explain()` prints the full
reasoning (press **F1** in the game, or type `:why` in the terminal version).

## The four requirements, and where they live

| Requirement | Shared code | Asterisk Slime (`ai/fsm.py`) | Sir Wherewell (`ai/knight.py`) |
|---|---|---|---|
| **State changes with switch cases** | `Goal.step()` and `CompositeGoal.process()` use `match` on the goal status (`ai/goals.py`); `steer()` uses `match` on the behaviour (`ai/steering.py`) | `transitions()`: one `case` per mood (opening, wobble, overcast, exhausted, careful) with the probabilities of design doc 5.3; `idle_movement()` | `next_mode()`: the stance machine (vigilant, pressing, besieged, desperate, winded) as a `match` with guards; `idle_movement()` |
| **Goal-driven behaviour** | `AtomicGoal`, `CompositeGoal`, `Think` with `Evaluator`s (Buckland, *Programming Game AI by Example*, ch. 9) | Four goals (splat, catch_breath, pant, careful); its mood weights them; a goal it cannot do (no MP) fails and Think replans | Six goals (execute, restore_ward, strip_ward, press, hold_line, catch_breath), each a multi-turn plan of subgoals; commitment, noise and a repetition penalty |
| **Perception** | `Perception.sense()` builds a read-only `Percept`: sight (HP, MP, wards, statuses), its own book (what it can afford) and a fading memory of Ada's casts (threat, weakness found) (`ai/perception.py`) | Below 30% HP it is desperate (always careful); with no MP it cannot splat; if Ada is exhausted it pounces | Raises his ward at the start; once Ada hits his weakness he becomes besieged, values the ward less and guards or counter-attacks; finishes a weak Ada; dispels a thick ward; rests without MP |
| **Steering behaviours** | `seek`, `flee`, `arrive`, `pursue`, `evade`, `wander` on a `Kinematic` body (Reynolds; Millington, *AI for Games*, ch. 3) (`ai/steering.py`) | Lunges (seek) to splat, creeps (arrive) when careful, returns to its puddle, wobbles (wander) while waiting | Charges (arrive) to strike, hunts (pursue) to finish Ada, falls back (arrive home) to raise a ward, keeps his distance (evade) when besieged, paces (wander) |

The brain chooses a `Movement` (behaviour + target) as part of each plan; the battle screen
(`engine/scenes.py`, `_update_body`) runs that steering every frame. Movement shows the
guardian's intention; it never changes a damage roll, and wandering uses the game's
visual-only random generator, so seeded battles stay reproducible.

## One turn of Sir Wherewell, step by step

1. **Perceive.** `Perception.sense(state)` reads both combatants and Ada's past casts
   (`BattleState.ada_casts`, written by `magic/battle.py` after each of her queries). It
   updates the threat estimate (an exponential moving average of the damage she deals) and
   notes when she last hit his weakness. That memory fades over three turns.
2. **Change stance.** `next_mode()` matches the current stance against the Percept: below
   30% HP he is desperate, without MP for a strike he is winded, and once she has found his
   weakness he is besieged.
3. **Think.** Each evaluator scores its goal from the Percept, and the stance multiplies it
   (`STANCE_BIAS`). Think keeps the current plan unless another one is at least 25% better
   (commitment), applies a random factor between 0.85 and 1.15 (non-determinism), and makes a
   plan that has just finished 0.55 times as attractive each time it is chosen again in a row
   (so he does not repeat one trick forever).
4. **Act.** The chosen plan runs its next subgoal. Repositioning subgoals only set a
   Movement; the next one emits the Intent (for example `heavy`). If a subgoal is no longer
   possible (no MP), the plan fails and Think picks another one, in the same turn.
5. **Express.** `render_knight()` writes a precise filter, e.g.
   `SELECT name FROM foe_spells WHERE foe_id = 2 AND kind = 'attack' AND power >= 20 AND power < 30 AND mp_cost <= 39`.
   It returns exactly one row, and its `WHERE` is the rune Ada learns from his first cast.

## Evaluation (design doc 9.1)

Three scripted players, 300 seeded battles each, against Sir Wherewell (200 HP):

| Player | Ada wins | Rounds | Ada HP left |
|---|---|---|---|
| Novice: `SELECT name FROM spells LIMIT 1`, never filters | 0% | 5.3 | 0 |
| Competent: copies WHERE, casts the first Storm attack | 58% | 6.3 | 10 |
| Expert: strongest Storm spell, Spark when low on MP, heals when hurt | 100% | 3.2 | 60 |

He beats the player who does not filter and loses to the one who does, which is the lesson
of his fight. The tests in `tests/test_guardians.py` check this on fixed seeds.
