import pytest

from lastmile.economics import (Seasonality, annuity_factor, breakeven_capex, payback_months,
                                rate_after_fuel_shock)


def test_cycles_per_year_range():
    s = Seasonality()
    lo, mid, hi = (s.cycles_per_year(c) for c in ("low", "mid", "high"))
    assert lo < mid < hi
    assert lo == pytest.approx(183 / 25 + 182 / 35)
    assert hi == pytest.approx(183 / 22 + 182 / 30)


def test_breakeven_and_payback():
    assert annuity_factor(0, 3) == 3
    assert breakeven_capex(10_000, 0.0, 2) == 20_000
    assert payback_months(20_000, 24_000) == pytest.approx(10)
    assert payback_months(20_000, 0) == float("inf")


def test_fuel_shock():
    assert rate_after_fuel_shock(19, 0.6, 0.0) == 19
    assert rate_after_fuel_shock(19, 0.5, 0.2) == pytest.approx(20.9)
