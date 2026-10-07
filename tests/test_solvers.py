import numpy as np
import pytest

from lastmile.model import Problem, TimeModel
from lastmile.solvers import RoutingEngine, clarke_wright, solve_ortools, two_opt
from lastmile.solvers.two_opt import two_opt_route


def test_clarke_wright_feasible_and_beats_out_and_back(nagpur):
    p = Problem(nagpur, 20)
    sol = clarke_wright(p).assert_feasible()
    assert sol.total_km < 2 * nagpur.depot_dist.sum()
    assert max(sol.loads) <= 20


def test_two_opt_never_worse(nagpur):
    sol = clarke_wright(Problem(nagpur, 20))
    better = two_opt(sol).assert_feasible()
    assert better.total_km <= sol.total_km + 1e-9
    for a, b in zip(sol.route_km, better.route_km):
        assert b <= a + 1e-9


def test_two_opt_fixes_crossing():
    # square: depot (0,0); points on a unit square visited in a crossing order
    pts = np.array([[0, 0], [0, 1], [1, 1], [1, 0]], float)
    d = np.linalg.norm(pts[:, None] - pts[None], axis=2)
    assert two_opt_route(d, [2, 1, 3]) in ([1, 2, 3], [3, 2, 1])


def test_duration_limit_respected_by_cw(nagpur):
    tm = TimeModel(speed_kmh=40, stop_min=20)
    p = Problem(nagpur, 20, tm, 600)
    sol = clarke_wright(p).assert_feasible()
    assert max(sol.durations_min()) <= 600 + 1e-9


@pytest.mark.slow
def test_ortools_capacity_and_duration(nagpur):
    tm = TimeModel(speed_kmh=40, stop_min=20)
    p = Problem(nagpur, 20, tm, 600)
    sol = solve_ortools(p, time_limit_s=2).assert_feasible()
    assert max(sol.durations_min()) <= 600 + 1e-9


@pytest.mark.slow
def test_engine_pool_makes_cost_monotone(nagpur):
    eng = RoutingEngine(ortools_time_limit_s=1, verbose=False)
    costs = [eng.best(Problem(nagpur, q)).total_km for q in (18, 19, 20, 21)]
    assert all(b <= a + 1e-9 for a, b in zip(costs, costs[1:]))


@pytest.mark.slow
def test_ortools_on_subset(nagpur):
    p = Problem(nagpur, 5, customers=tuple(range(1, 21)))
    sol = solve_ortools(p, time_limit_s=1).assert_feasible()
    assert sorted(i for r in sol.routes for i in r) == list(range(1, 21))
