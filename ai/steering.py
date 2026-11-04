"""Steering behaviours: how a guardian moves on the battlefield.

Technique: Reynolds' steering behaviours (seek, flee, arrive, pursue, evade, wander), in the
"dynamic" form of Millington, "AI for Games", 3rd ed., ch. 3: each behaviour returns an
acceleration, and a Kinematic body integrates it with a capped speed.
A brain chooses a Movement (which behaviour, towards whom) as part of each plan; the screen
then runs the steering every frame. Movement is how the guardian shows its intention (it
charges to strike, falls back to raise a ward, prowls while it waits); it never changes a
damage roll, so any random wander uses the game's visual-only rng.
Pure Python, no pygame.

STATUS: vectors, kinematic bodies, six behaviours and a dispatcher.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Vec:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, o: "Vec") -> "Vec":
        return Vec(self.x + o.x, self.y + o.y)

    def __sub__(self, o: "Vec") -> "Vec":
        return Vec(self.x - o.x, self.y - o.y)

    def __mul__(self, k: float) -> "Vec":
        return Vec(self.x * k, self.y * k)

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> "Vec":
        n = self.length()
        return Vec(self.x / n, self.y / n) if n else Vec()

    def truncated(self, limit: float) -> "Vec":
        n = self.length()
        return self * (limit / n) if n > limit else self


@dataclass(frozen=True)
class Movement:
    """A brain's movement order: a behaviour and the name of what it is about."""
    behaviour: str            # seek | flee | arrive | pursue | evade | wander | hold
    target: str = "home"      # "ada", "home" or "front" (the striking spot before Ada)


@dataclass
class Kinematic:
    position: Vec
    velocity: Vec = Vec()
    max_speed: float = 60.0           # pixels per second
    max_accel: float = 220.0          # pixels per second squared

    def integrate(self, accel: Vec, dt: float) -> None:
        """Newton-Euler step (Millington 3.1): v += a dt, capped; p += v dt."""
        accel = accel.truncated(self.max_accel)
        self.velocity = (self.velocity + accel * dt).truncated(self.max_speed)
        self.position = self.position + self.velocity * dt


@dataclass
class WanderState:
    angle: float = 0.0


# ------------------------------------------------------------------ the behaviours

def seek(agent: Kinematic, target: Vec) -> Vec:
    return (target - agent.position).normalized() * agent.max_accel


def flee(agent: Kinematic, threat: Vec) -> Vec:
    return (agent.position - threat).normalized() * agent.max_accel


def arrive(agent: Kinematic, target: Vec, slow_radius: float = 30.0,
           stop_radius: float = 1.5, time_to_target: float = 0.15) -> Vec:
    """Seek, but brake inside slow_radius so the body stops on the spot instead of orbiting."""
    offset = target - agent.position
    distance = offset.length()
    if distance < stop_radius:
        return agent.velocity * (-1 / time_to_target)     # cancel the remaining speed
    speed = agent.max_speed if distance > slow_radius else agent.max_speed * distance / slow_radius
    desired = offset.normalized() * speed
    return (desired - agent.velocity) * (1 / time_to_target)


def pursue(agent: Kinematic, target: Kinematic, max_prediction: float = 0.6) -> Vec:
    """Seek where the target will be, not where it is."""
    distance = (target.position - agent.position).length()
    speed = agent.velocity.length()
    prediction = max_prediction if speed <= distance / max_prediction else distance / speed
    return seek(agent, target.position + target.velocity * prediction)


def evade(agent: Kinematic, threat: Kinematic, max_prediction: float = 0.6) -> Vec:
    distance = (threat.position - agent.position).length()
    speed = agent.velocity.length()
    prediction = max_prediction if speed <= distance / max_prediction else distance / speed
    return flee(agent, threat.position + threat.velocity * prediction)


def wander(agent: Kinematic, home: Vec, state: WanderState, rng: random.Random,
           radius: float = 14.0, jitter: float = 0.9) -> Vec:
    """Drift around home: a target slides randomly on a circle around it (Reynolds' wander,
    tethered so the guardian prowls near its post instead of walking off the screen)."""
    state.angle += rng.uniform(-jitter, jitter)
    spot = home + Vec(math.cos(state.angle), math.sin(state.angle) * 0.4) * radius
    return arrive(agent, spot, slow_radius=20.0)


def steer(order: Movement, agent: Kinematic, places: dict[str, Kinematic],
          wander_state: WanderState, rng: random.Random) -> Vec:
    """Run one Movement order. places maps target names to bodies ("ada", "home", "front")."""
    target = places.get(order.target, places["home"])
    match order.behaviour:
        case "seek":
            return seek(agent, target.position)
        case "flee":
            return flee(agent, target.position)
        case "arrive":
            return arrive(agent, target.position)
        case "pursue":
            return pursue(agent, target)
        case "evade":
            return evade(agent, target)
        case "wander":
            return wander(agent, target.position, wander_state, rng)
        case _:                                                 # "hold": brake to a stop
            return agent.velocity * -4.0
