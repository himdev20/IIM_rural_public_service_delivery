"""Repair a solution so it becomes feasible for a *tighter* problem.

Used by the downward pass of the continuation sweep: the best solution at
capacity Q+1 (or a looser time limit) is turned into a feasible starting point
at Q, which OR-Tools then improves. Steps:

1. From every route that violates capacity or duration, remove the stops whose
   removal saves the most distance until the route is feasible.
2. Re-insert each removed stop at its cheapest feasible position in any route,
   opening a new route when none fits.
"""

from __future__ import annotations

from ..data import DEPOT
from ..model import Problem, Solution, route_load


def _feasible(problem: Problem, route: list[int]) -> bool:
    inst = problem.instance
    if route_load(inst, route) > problem.capacity:
        return False
    if problem.has_duration_limit:
        return problem.time.route_duration_min(inst, route) <= problem.max_duration_min + 1e-9
    return True


def repair(solution: Solution, problem: Problem) -> Solution | None:
    """Return a feasible solution for `problem` built from `solution`, or None."""
    d = problem.instance.dist
    routes = [list(r) for r in solution.routes]
    removed: list[int] = []
    for r in routes:
        while r and not _feasible(problem, r):
            path = [DEPOT, *r, DEPOT]
            gains = [d[path[k - 1], path[k]] + d[path[k], path[k + 1]] - d[path[k - 1], path[k + 1]]
                     for k in range(1, len(path) - 1)]
            removed.append(r.pop(max(range(len(r)), key=gains.__getitem__)))
    routes = [r for r in routes if r]

    # far-from-depot stops first: they are the hardest to place
    for node in sorted(removed, key=lambda i: -d[DEPOT, i]):
        best = None
        for ri, r in enumerate(routes):
            path = [DEPOT, *r, DEPOT]
            for k in range(len(path) - 1):
                delta = d[path[k], node] + d[node, path[k + 1]] - d[path[k], path[k + 1]]
                if best is not None and delta >= best[0]:
                    continue
                cand = r[:k] + [node] + r[k:]
                if _feasible(problem, cand):
                    best = (delta, ri, k)
        if best is None:
            if not _feasible(problem, [node]):
                return None
            routes.append([node])
        else:
            _, ri, k = best
            routes[ri].insert(k, node)
    out = Solution(problem, routes, method="repair")
    return out if out.is_feasible else None

