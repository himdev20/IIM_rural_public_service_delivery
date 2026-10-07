"""Google OR-Tools routing solver (capacity + optional route-duration limit).

* Distances are scaled to integers (x100; the data have at most 2 decimals).
* Travel + service times are rounded *up* to 0.1 minute, so any route OR-Tools
  accepts is also feasible under exact arithmetic.
* Each OR-Tools "vehicle" is one route (one trip of the single hired truck);
  with a per-km hire contract, unused vehicles cost nothing.
* Search: a first-solution strategy (default SAVINGS) followed by Guided Local
  Search for ``time_limit_s`` seconds. Optionally warm-started from routes.
"""

from __future__ import annotations

import math
import time as _time
from typing import Sequence

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from ..data import DEPOT
from ..model import Problem, Solution

DIST_SCALE = 100
TIME_SCALE = 10  # deci-minutes


def _n_vehicles(problem: Problem, nodes: Sequence[int]) -> int:
    inst = problem.instance
    demand = sum(int(inst.demand[i]) for i in nodes)
    lb = math.ceil(demand / problem.capacity)
    if problem.has_duration_limit:
        t = problem.time
        work = sum(t.service_min(inst.demand[i]) + t.drive_min(inst.depot_dist[i]) for i in nodes)
        lb = max(lb, math.ceil(work / problem.max_duration_min))
    return min(len(nodes), max(lb + 4, math.ceil(1.5 * lb)))


def solve_ortools(problem: Problem, time_limit_s: float = 15, first_solution: str = "SAVINGS",
                  initial_routes: list[list[int]] | None = None,
                  n_vehicles: int | None = None) -> Solution | None:
    inst = problem.instance
    nodes = list(problem.nodes)
    local = [DEPOT, *nodes]                      # local index -> node id
    pos = {node: k for k, node in enumerate(local)}
    n_vehicles = n_vehicles or _n_vehicles(problem, nodes)
    if initial_routes:
        n_vehicles = max(n_vehicles, len(initial_routes) + 2)

    sub = inst.dist[np.ix_(local, local)]
    dist_int = np.rint(sub * DIST_SCALE).astype(np.int64)

    manager = pywrapcp.RoutingIndexManager(len(local), n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)
    cost_cb = routing.RegisterTransitMatrix(dist_int.tolist())
    routing.SetArcCostEvaluatorOfAllVehicles(cost_cb)

    demand = [0] + [int(inst.demand[i]) for i in nodes]
    demand_cb = routing.RegisterUnaryTransitVector(demand)
    routing.AddDimensionWithVehicleCapacity(demand_cb, 0, [problem.capacity] * n_vehicles,
                                            True, "Load")

    if problem.has_duration_limit:
        t = problem.time
        service = np.array([t.depot_min] + [t.service_min(inst.demand[i]) for i in nodes])
        minutes = sub / t.speed_kmh * 60.0 + service[:, None]   # service at the origin node
        time_int = np.ceil(minutes * TIME_SCALE - 1e-9).astype(np.int64)
        time_cb = routing.RegisterTransitMatrix(time_int.tolist())
        horizon = int(math.floor(problem.max_duration_min * TIME_SCALE + 1e-9))
        routing.AddDimension(time_cb, 0, horizon, True, "Time")

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = getattr(routing_enums_pb2.FirstSolutionStrategy, first_solution)
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    params.time_limit.FromMilliseconds(max(int(time_limit_s * 1000), 100))

    start = _time.perf_counter()
    assignment = None
    if initial_routes:
        routing.CloseModelWithParameters(params)
        init = [[pos[i] for i in r] for r in initial_routes] + [[]] * (n_vehicles - len(initial_routes))
        warm = routing.ReadAssignmentFromRoutes(init, True)
        if warm is not None:
            assignment = routing.SolveFromAssignmentWithParameters(warm, params)
    if assignment is None:
        if initial_routes:  # model already closed: rebuild without warm start
            return solve_ortools(problem, time_limit_s, first_solution, None, n_vehicles)
        assignment = routing.SolveWithParameters(params)
    elapsed = _time.perf_counter() - start

    if assignment is None:
        if first_solution != "PATH_CHEAPEST_ARC":
            return solve_ortools(problem, time_limit_s, "PATH_CHEAPEST_ARC", None, n_vehicles)
        if n_vehicles < len(nodes):
            return solve_ortools(problem, time_limit_s, first_solution, None,
                                 min(len(nodes), 2 * n_vehicles))
        return None

    routes = []
    for v in range(n_vehicles):
        idx = routing.Start(v)
        route = []
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node != 0:
                route.append(local[node])
            idx = assignment.Value(routing.NextVar(idx))
        if route:
            routes.append(route)
    return Solution(problem, routes, method="ortools",
                    meta={"time_limit_s": time_limit_s, "first_solution": first_solution,
                          "warm_start": bool(initial_routes), "seconds": round(elapsed, 2)})
