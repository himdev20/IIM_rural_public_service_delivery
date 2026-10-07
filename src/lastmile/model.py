"""Problem and solution objects shared by all solvers and analyses.

A :class:`Problem` is an :class:`~lastmile.data.Instance` plus constraints:

* ``capacity`` -- cryocans per truck load (Q);
* ``time`` and ``max_duration_min`` -- an optional route-duration limit
  (e.g. depart 8 a.m., return 6 p.m. = 600 minutes);
* ``customers`` -- which locations must be served (default: all). Used for
  "with / without village i" marginal-cost calculations.

A :class:`Solution` is a list of routes (each a list of node ids, depot omitted).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterable, Sequence

import numpy as np

from .data import DEPOT, Instance


# ---------------------------------------------------------------------------
# Time model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TimeModel:
    """Converts a route into a duration. All parameters are assumptions.

    duration = depot_min + driving km / speed + sum over stops of
               (stop_min + extra_unit_min * (demand - 1))
    """

    speed_kmh: float = 40.0
    stop_min: float = 20.0
    depot_min: float = 0.0
    extra_unit_min: float = 5.0

    def service_min(self, demand: int) -> float:
        return self.stop_min + self.extra_unit_min * max(int(demand) - 1, 0)

    def drive_min(self, km: float) -> float:
        return km / self.speed_kmh * 60.0

    def route_duration_min(self, inst: Instance, route: Sequence[int], km: float | None = None) -> float:
        km = route_distance(inst, route) if km is None else km
        service = sum(self.service_min(inst.demand[i]) for i in route)
        return self.depot_min + self.drive_min(km) + service

    def label(self) -> str:
        return f"{self.speed_kmh:g}kmh-{self.stop_min:g}min"


# ---------------------------------------------------------------------------
# Problem
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Problem:
    instance: Instance
    capacity: int
    time: TimeModel | None = None
    max_duration_min: float | None = None
    customers: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.max_duration_min is not None and self.time is None:
            raise ValueError("A duration limit needs a TimeModel")
        if self.customers is not None:
            object.__setattr__(self, "customers", tuple(sorted(self.customers)))

    @property
    def nodes(self) -> tuple[int, ...]:
        """Customers that must be served."""
        return self.customers if self.customers is not None else self.instance.customers

    @property
    def has_duration_limit(self) -> bool:
        return self.max_duration_min is not None

    def without(self, node: int) -> "Problem":
        return Problem(self.instance, self.capacity, self.time, self.max_duration_min,
                       tuple(c for c in self.nodes if c != node))

    def with_capacity(self, capacity: int) -> "Problem":
        return Problem(self.instance, capacity, self.time, self.max_duration_min, self.customers)

    def key(self) -> str:
        """Deterministic identifier used for caching solutions on disk."""
        payload = {
            "inst": self.instance.fingerprint(),
            "Q": self.capacity,
            "time": None if self.time is None else [self.time.speed_kmh, self.time.stop_min,
                                                    self.time.depot_min, self.time.extra_unit_min],
            "H": self.max_duration_min,
            "cust": None if self.customers is None else hashlib.sha1(
                json.dumps(self.customers).encode()).hexdigest()[:10],
        }
        return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def describe(self) -> str:
        h = "none" if self.max_duration_min is None else f"{self.max_duration_min / 60:g}h"
        t = "" if self.time is None else f", {self.time.label()}"
        return f"Q={self.capacity}, H={h}{t}, n={len(self.nodes)}"


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------
def route_distance(inst: Instance, route: Sequence[int]) -> float:
    if not route:
        return 0.0
    path = [DEPOT, *route, DEPOT]
    d = inst.dist
    return float(sum(d[a, b] for a, b in zip(path[:-1], path[1:])))


def route_load(inst: Instance, route: Sequence[int]) -> int:
    return int(sum(inst.demand[i] for i in route))


@dataclass
class Solution:
    """A set of routes for a problem, with lazily computed statistics."""

    problem: Problem
    routes: list[list[int]]
    method: str = ""
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.routes = [list(map(int, r)) for r in self.routes if len(r) > 0]

    # ----------------------------------------------------------- statistics
    @cached_property
    def route_km(self) -> list[float]:
        return [route_distance(self.problem.instance, r) for r in self.routes]

    @cached_property
    def loads(self) -> list[int]:
        return [route_load(self.problem.instance, r) for r in self.routes]

    @property
    def total_km(self) -> float:
        return float(sum(self.route_km))

    @property
    def n_routes(self) -> int:
        return len(self.routes)

    def durations_min(self, time: TimeModel | None = None) -> list[float]:
        time = time or self.problem.time or TimeModel()
        inst = self.problem.instance
        return [time.route_duration_min(inst, r, km) for r, km in zip(self.routes, self.route_km)]

    # ------------------------------------------------------------- validity
    def violations(self, tol: float = 1e-6) -> list[str]:
        p = self.problem
        issues: list[str] = []
        served = [i for r in self.routes for i in r]
        if sorted(served) != sorted(p.nodes):
            missing = set(p.nodes) - set(served)
            extra = [i for i in set(served) if served.count(i) > 1 or i not in p.nodes]
            issues.append(f"coverage: missing={sorted(missing)[:10]} duplicate/extra={sorted(extra)[:10]}")
        for k, load in enumerate(self.loads):
            if load > p.capacity:
                issues.append(f"route {k}: load {load} > capacity {p.capacity}")
        if p.has_duration_limit:
            for k, dur in enumerate(self.durations_min()):
                if dur > p.max_duration_min + tol:
                    issues.append(f"route {k}: duration {dur:.1f} > {p.max_duration_min:.1f} min")
        return issues

    @property
    def is_feasible(self) -> bool:
        return not self.violations()

    def assert_feasible(self) -> "Solution":
        issues = self.violations()
        if issues:
            raise AssertionError(f"{self.method} infeasible for {self.problem.describe()}: {issues[:3]}")
        return self

    def rebind(self, problem: Problem, method: str | None = None) -> "Solution":
        """Same routes, evaluated against another problem (e.g. a different Q)."""
        return Solution(problem, [list(r) for r in self.routes], method or self.method, dict(self.meta))

    # -------------------------------------------------------- service balance
    def balance_stats(self, time: TimeModel | None = None,
                      overnight_threshold_min: float = 600.0) -> dict[str, float]:
        """Route-length balance and same-day-return statistics."""
        km = np.array(self.route_km)
        dur = np.array(self.durations_min(time))
        return {
            "n_routes": float(self.n_routes),
            "total_km": float(km.sum()),
            "max_route_km": float(km.max()),
            "min_route_km": float(km.min()),
            "cv_route_km": float(km.std(ddof=0) / km.mean()),
            "max_duration_h": float(dur.max() / 60),
            "overnight_routes": float((dur > overnight_threshold_min + 1e-9).sum()),
            "truck_days": float(sum(math.ceil(d / overnight_threshold_min - 1e-9) for d in dur)),
            "max_load": float(max(self.loads)),
        }

    # -------------------------------------------------------------- serialise
    def to_dict(self) -> dict:
        return {"method": self.method, "total_km": round(self.total_km, 4),
                "routes": self.routes, "meta": self.meta}

    def summary(self) -> str:
        return (f"{self.method:<22} {self.total_km:9.1f} km  routes={self.n_routes:3d}  "
                f"max load={max(self.loads)}  feasible={self.is_feasible}")


def best_of(solutions: Iterable[Solution]) -> Solution:
    """Cheapest *feasible* solution; ties keep the first one supplied."""
    feasible = [s for s in solutions if s is not None and s.is_feasible]
    if not feasible:
        raise ValueError("no feasible solution among candidates")
    return min(feasible, key=lambda s: round(s.total_km, 6))
