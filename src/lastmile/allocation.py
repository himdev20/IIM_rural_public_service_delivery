"""Who bears the cost? Allocation of route costs to locations.

Two complementary measures are implemented.

**Marginal cost** (system level): MC_i = C(N) - C(N minus i), where C is the
best cost found for serving a set of locations. It answers "how much cheaper
would the network be without village i?" and is computed in
:mod:`lastmile.analysis.c4_incidence` by re-optimisation.

**Shapley value** (route level, exact): within a route served in a fixed order
0 -> x1 -> ... -> xm -> 0, the cost of serving a subset S in the same order is

    v(S) = sum over consecutive members (a, b) of S, with depot at both ends, d(a, b).

Every term "edge (a, b) is used" equals 1 exactly when a and b are in S and none
of the k locations strictly between them is. For such a game the Shapley value
has a closed form (|T| = number of non-depot end points of the edge):

    player in T : (|T|-1)! k! / (|T|+k)!      (it "completes" the edge)
    player in K : -|T|! (k-1)! / (|T|+k)!     (it "breaks" the edge)

Summing over edges gives the exact Shapley value in O(m^3) per route. The
allocation is efficient (it sums to the route length) and needs no sampling.
"""

from __future__ import annotations

from math import factorial

import numpy as np

from .data import DEPOT
from .model import Solution


def route_shapley(dist: np.ndarray, route: list[int]) -> dict[int, float]:
    """Exact Shapley allocation of one route's length among its locations."""
    path = [DEPOT, *route, DEPOT]
    m = len(route)
    phi = np.zeros(m + 2)  # positions; 0 and m+1 are the depot
    for a in range(m + 2):
        for b in range(a + 1, m + 2):
            w = dist[path[a], path[b]]
            if w == 0:
                continue
            ends = [p for p in (a, b) if p not in (0, m + 1)]
            t, k = len(ends), b - a - 1
            if t == 0:
                continue  # depot-to-depot edge: v(empty set) term, length 0 in practice
            denom = factorial(t + k)
            for p in ends:
                phi[p] += w * factorial(t - 1) * factorial(k) / denom
            if k:
                share = w * factorial(t) * factorial(k - 1) / denom
                phi[a + 1:b] -= share
    return {node: float(phi[pos + 1]) for pos, node in enumerate(route)}


def shapley_allocation(solution: Solution) -> dict[int, float]:
    """Shapley share (km) of every location, route by route."""
    dist = solution.problem.instance.dist
    out: dict[int, float] = {}
    for route in solution.routes:
        out.update(route_shapley(dist, route))
    return out


def detour_cost(solution: Solution) -> dict[int, float]:
    """Insertion (detour) cost d(prev,i) + d(i,next) - d(prev,next) in the given solution."""
    d = solution.problem.instance.dist
    out = {}
    for route in solution.routes:
        path = [DEPOT, *route, DEPOT]
        for k in range(1, len(path) - 1):
            a, i, b = path[k - 1], path[k], path[k + 1]
            out[i] = float(d[a, i] + d[i, b] - d[a, b])
    return out


def concentration(values: np.ndarray, order_by: np.ndarray, top_share: float = 0.2) -> dict[str, float]:
    """Share of total cost borne by the `top_share` of locations ranked by `order_by`,
    plus a Gini coefficient of the (non-negative part of the) allocation."""
    values = np.asarray(values, float)
    order = np.argsort(-np.asarray(order_by, float))
    k = max(1, int(round(top_share * len(values))))
    total = values.sum()
    v = np.sort(np.clip(values, 0, None))
    n = len(v)
    gini = float((2 * np.arange(1, n + 1) - n - 1) @ v / (n * v.sum())) if v.sum() > 0 else 0.0
    return {"top_share_of_cost": float(values[order[:k]].sum() / total), "gini": gini}
