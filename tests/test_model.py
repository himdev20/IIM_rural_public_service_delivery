import pytest

from lastmile.model import Problem, Solution, TimeModel, route_distance


def test_time_model_duration(abc):
    tm = TimeModel(speed_kmh=60, stop_min=10, depot_min=5, extra_unit_min=0)
    # depot->C2 (8) ->C1 (9) ->depot (12) = 29 km = 29 min at 60 km/h, 2 stops, 5 min depot
    assert tm.route_duration_min(abc, [2, 1]) == pytest.approx(29 + 20 + 5)


def test_extra_units_add_service_time(abc):
    tm = TimeModel(speed_kmh=60, stop_min=10, extra_unit_min=5)
    assert tm.service_min(1) == 10 and tm.service_min(3) == 20


def test_violations_detected(abc):
    p = Problem(abc, 100)
    sol = Solution(p, [[1, 2, 3], [4, 5, 6, 7, 8, 9, 10, 11, 12, 13]])
    assert any("load" in v for v in sol.violations())
    sol2 = Solution(p, [[1, 2]])
    assert any("coverage" in v for v in sol2.violations())


def test_route_distance_symmetric(abc):
    assert route_distance(abc, [1, 2, 3]) == route_distance(abc, [3, 2, 1])


def test_problem_without(abc):
    p = Problem(abc, 200).without(5)
    assert 5 not in p.nodes and len(p.nodes) == 12
    assert p.key() != Problem(abc, 200).key()
