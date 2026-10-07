"""Intra-route 2-opt improvement (Croes, 1958).

Each route is improved independently by reversing segments while that shortens
it. Loads do not change and every accepted move shortens the route, so a route
that satisfied the duration limit before still satisfies it afterwards.
"""

from __future__ import annotations

import numpy as np

from ..data import DEPOT
from ..model import Solution


def two_opt_route(dist: np.ndarray, route: list[int], tol: float = 1e-9) -> list[int]:
    """Best-improvement 2-opt on one route (depot fixed at both ends)."""
    path = [DEPOT, *route, DEPOT]
    n = len(path)
    if n <= 4:
        return list(route)
    improved = True
    while improved:
        improved = False
        best_delta, best_move = -tol, None
        for i in range(0, n - 3):
            a, b = path[i], path[i + 1]
            for k in range(i + 2, n - 1):
                c, d = path[k], path[k + 1]
                delta = dist[a, c] + dist[b, d] - dist[a, b] - dist[c, d]
                if delta < best_delta:
                    best_delta, best_move = delta, (i, k)
        if best_move is not None:
            i, k = best_move
            path[i + 1:k + 1] = path[i + 1:k + 1][::-1]
            improved = True
    return path[1:-1]


def two_opt(solution: Solution) -> Solution:
    dist = solution.problem.instance.dist
    routes = [two_opt_route(dist, r) for r in solution.routes]
    method = f"{solution.method}+2opt" if solution.method else "2opt"
    return Solution(solution.problem, routes, method=method, meta=dict(solution.meta))
