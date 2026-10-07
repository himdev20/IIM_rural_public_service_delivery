"""Exact route Shapley vs brute force on small routes."""

import itertools
from math import factorial

import numpy as np
import pytest

from lastmile.allocation import concentration, route_shapley


def _v(dist, route, subset):
    path = [0] + [x for x in route if x in subset] + [0]
    return sum(dist[a, b] for a, b in zip(path, path[1:]))


def _brute(dist, route):
    n = len(route)
    phi = {i: 0.0 for i in route}
    for i in route:
        others = [x for x in route if x != i]
        for r in range(n):
            for S in itertools.combinations(others, r):
                w = factorial(r) * factorial(n - r - 1) / factorial(n)
                phi[i] += w * (_v(dist, route, set(S) | {i}) - _v(dist, route, set(S)))
    return phi


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_route_shapley_matches_brute_force(seed):
    rng = np.random.default_rng(seed)
    m = 7
    d = rng.uniform(1, 30, (m + 1, m + 1))
    d = (d + d.T) / 2
    np.fill_diagonal(d, 0)                       # deliberately NOT metric
    route = list(rng.permutation(np.arange(1, m + 1)))
    exact, brute = route_shapley(d, route), _brute(d, route)
    for i in route:
        assert exact[i] == pytest.approx(brute[i], abs=1e-9)
    assert sum(exact.values()) == pytest.approx(_v(d, route, set(route)))  # efficiency


def test_concentration_bounds():
    vals = np.array([1, 1, 1, 1, 6.0])
    c = concentration(vals, order_by=np.arange(5), top_share=0.2)
    assert c["top_share_of_cost"] == pytest.approx(0.6)
    assert 0 < c["gini"] < 1
