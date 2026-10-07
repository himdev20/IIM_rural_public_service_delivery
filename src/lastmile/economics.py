"""Turning kilometres per delivery cycle into rupees per year.

A *cycle* is one visit to every location (all routes run once). The case says
routes are repeated every 22-25 days in summer and every 30-35 days in winter,
so the number of cycles per year is a range, not a number.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Seasonality:
    summer_days: float = 183
    summer_interval: tuple[float, float] = (22, 25)
    winter_days: float = 182
    winter_interval: tuple[float, float] = (30, 35)

    @classmethod
    def from_settings(cls, s) -> "Seasonality":
        return cls(s.summer_days, tuple(s.summer_interval_days), s.winter_days,
                   tuple(s.winter_interval_days))

    def cycles_per_year(self, case: str = "mid") -> float:
        """'low' = longest intervals, 'high' = shortest, 'mid' = midpoints."""
        pick = {"low": lambda iv: iv[1], "high": lambda iv: iv[0],
                "mid": lambda iv: (iv[0] + iv[1]) / 2}[case]
        return self.summer_days / pick(self.summer_interval) + self.winter_days / pick(self.winter_interval)

    def cycles_range(self) -> dict[str, float]:
        return {c: self.cycles_per_year(c) for c in ("low", "mid", "high")}


def annual_cost(km_per_cycle: float, rate_per_km: float, cycles_per_year: float) -> float:
    return km_per_cycle * rate_per_km * cycles_per_year


def annuity_factor(rate: float, years: float) -> float:
    """Present value of Rs 1 per year for `years` years (end-of-year payments)."""
    if rate == 0:
        return float(years)
    return (1 - (1 + rate) ** (-years)) / rate


def breakeven_capex(annual_saving: float, rate: float, years: float) -> float:
    """Most one should pay up-front for a stream of annual savings."""
    return annual_saving * annuity_factor(rate, years)


def payback_months(capex: float, annual_saving: float) -> float:
    """Simple (undiscounted) payback period in months; inf if no saving."""
    return float("inf") if annual_saving <= 0 else 12.0 * capex / annual_saving


def rate_after_fuel_shock(base_rate: float, fuel_share: float, shock: float) -> float:
    """Per-km rate when the fuel component of the rate moves by `shock` (e.g. +0.2)."""
    return base_rate * (1 + fuel_share * shock)
