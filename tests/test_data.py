import numpy as np

from lastmile.data import load_status_quo, savings_matrix


def test_nagpur_shape_and_demand(nagpur):
    assert nagpur.n == 177
    assert nagpur.dist.shape == (178, 178)
    assert np.allclose(nagpur.dist, nagpur.dist.T)
    assert (nagpur.demand[1:] == 1).all() and nagpur.demand[0] == 0
    assert nagpur.labels[0] == "FSL" and nagpur.labels[3] == "Shankarpur"


def test_text_cells_detected(nagpur):
    # The workbook stores a handful of distances as text; the VBA sort depends on it.
    assert (149, 45) in nagpur.text_cells and (172, 71) in nagpur.text_cells


def test_status_quo_table(case_file):
    routes = load_status_quo(case_file)
    assert len(routes) == 9
    assert sum(r.reported_km for r in routes) == 2602
    served = sorted(i for r in routes for i in r.sequence)
    assert served == list(range(1, 178))


def test_abc_savings_matrix_matches_teaching_pdf(abc):
    """The ABC warehouse PDF prints the savings matrix; ours must match it."""
    s = savings_matrix(abc)
    printed = {(2, 1): 11, (3, 1): 21, (4, 3): 28, (6, 5): 29, (7, 6): 33,
               (11, 6): 34, (11, 10): 32, (13, 12): 18, (9, 1): 0, (13, 1): 0}
    for (i, j), v in printed.items():
        assert s[i, j] == v


def test_metric_closure_never_longer(nagpur):
    closed = nagpur.metric_closure()
    assert (closed.dist <= nagpur.dist + 1e-9).all()
    assert 0.5 < nagpur.triangle_violation_share() < 0.65
    assert closed.triangle_violation_share() == 0
