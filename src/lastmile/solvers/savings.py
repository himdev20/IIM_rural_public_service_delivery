"""Parallel Clarke-Wright savings heuristic (Clarke & Wright, 1964).

Textbook version: start with one out-and-back route per location, scan pairs by
decreasing saving s(i,j) = d(0,i) + d(0,j) - d(i,j), and join the two routes
containing i and j when (a) i and j are route ends, (b) the routes differ,
(c) the merged load fits the capacity and (d) the merged route respects the
duration limit, if any. Only positive savings are used.

Differences from the spreadsheet macro are deliberate (see ``savings_vba``):
every pair is examined, non-positive savings are ignored, and the duration
limit is supported.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from ..model import Problem, Solution, route_distance
from .savings_vba import vba_sorted_pairs

TieBreak = Literal["standard", "vba"]


def _ordered_pairs(problem: Problem, tie_break: TieBreak) -> list[tuple[int, int]]:
    inst = problem.instance
    nodes = set(problem.nodes)
    if tie_break == "vba":
        return [(i, j) for i, j in vba_sorted_pairs(inst) if i in nodes and j in nodes]
    d0 = inst.depot_dist
    idx = np.array(sorted(nodes))
    ii, jj = np.triu_indices(len(idx), k=1)
    a, b = idx[jj], idx[ii]  # a > b, same orientation as the spreadsheet
    s = np.round(d0[a] + d0[b] - inst.dist[a, b], 6)
    order = np.lexsort((b, a, inst.dist[a, b], -s))
    return [(int(a[k]), int(b[k])) for k in order]


def clarke_wright(problem: Problem, tie_break: TieBreak = "standard",
                  positive_only: bool = True) -> Solution:
    inst = problem.instance
    d0 = inst.depot_dist
    time, limit = problem.time, problem.max_duration_min

    routes: dict[int, list[int]] = {i: [i] for i in problem.nodes}
    route_of = {i: i for i in problem.nodes}
    load = {i: int(inst.demand[i]) for i in problem.nodes}
    km = {i: 2.0 * d0[i] for i in problem.nodes}

    if any(q > problem.capacity for q in load.values()):
        raise ValueError("a single location's demand exceeds the vehicle capacity")

    def duration_ok(route: list[int], route_km: float) -> bool:
        return limit is None or time.route_duration_min(inst, route, route_km) <= limit + 1e-9

    for i, j in _ordered_pairs(problem, tie_break):
        saving = d0[i] + d0[j] - inst.dist[i, j]
        if positive_only and saving <= 1e-12:
            break
        ri, rj = route_of[i], route_of[j]
        if ri == rj or load[ri] + load[rj] > problem.capacity:
            continue
        a, b = routes[ri], routes[rj]
        if i not in (a[0], a[-1]) or j not in (b[0], b[-1]):
            continue  # interior node: cannot be linked
        left = a if a[-1] == i else a[::-1]   # ... -> i
        right = b if b[0] == j else b[::-1]   # j -> ...
        merged = left + right
        merged_km = km[ri] + km[rj] - saving
        if not duration_ok(merged, merged_km):
            continue
        routes[ri] = merged
        load[ri] += load.pop(rj)
        km[ri] = merged_km
        del routes[rj], km[rj]
        for node in right:
            route_of[node] = ri

    ordered = sorted(routes.values(), key=lambda r: -route_distance(inst, r))
    return Solution(problem, ordered, method="cw", meta={"tie_break": tie_break})
