"""Component 0: the Python rebuild must reproduce the spreadsheet exactly."""

import pytest

from lastmile.data import load_spreadsheet_solution, load_spreadsheet_sort
from lastmile.model import Problem, route_distance
from lastmile.data import load_status_quo
from lastmile.solvers.savings_vba import solve_vba, vba_sorted_pairs


def test_sort_order_identical_to_workbook(nagpur, model_file):
    assert vba_sorted_pairs(nagpur) == load_spreadsheet_sort(model_file)


@pytest.mark.parametrize("capacity,sheet,target", [(20, "Sheet20", 2336.7), (25, "Sheet25", 2237.5)])
def test_spreadsheet_solutions_reproduced(nagpur, model_file, capacity, sheet, target):
    sol = solve_vba(Problem(nagpur, capacity))
    ref = load_spreadsheet_solution(model_file, sheet)
    assert sol.is_feasible
    assert sol.total_km == pytest.approx(target, abs=1e-9)
    assert ref["total_km"] == pytest.approx(target, abs=1e-9)
    assert sol.routes == ref["routes"]                       # same routes, same order, same direction
    assert [round(k, 4) for k in sol.route_km] == ref["route_km"]


def test_status_quo_distance(nagpur, case_file):
    routes = load_status_quo(case_file)
    assert sum(r.reported_km for r in routes) == 2602             # Table 1 as published
    measured = sum(route_distance(nagpur, r.sequence) for r in routes)
    assert measured == pytest.approx(2600.5)                      # same routes on the matrix
