"""Component 2 -- capacity-cost trade-off and the marginal value of capacity.

* C(Q): best cost per delivery cycle for every Q in [q_min, q_max].
* MV(Q) = C(Q-1) - C(Q): km saved by the Q-th cryocan slot.
* Break-even curve: the most the department should pay (up-front) to move from
  the baseline Q=20 to Q, i.e. the present value of the annual saving
  (C(20) - C(Q)) x rate x cycles/yr over a horizon. There are no cost data for
  larger trucks, so this is the honest substitute for an "optimal capacity".
* The actual Rs 20,000 retrofit (Q=25, possibly 26) is evaluated against it.
"""

from __future__ import annotations

import pandas as pd

from .. import plotting
from ..economics import breakeven_capex, payback_months
from ..model import Solution
from .common import Context


def capacity_sweep(ctx: Context, shift_hours: float | None = None, *,
                   speed_kmh: float | None = None, stop_min: float | None = None,
                   capacities: list[int] | None = None) -> tuple[pd.DataFrame, dict[int, Solution]]:
    """Best C(Q) for each Q via the engine's continuation sweep (equal effort per Q)."""
    c = ctx.settings.capacity
    e = ctx.settings.economics
    qs = set(capacities or range(c.q_min, c.q_max + 1))
    qs |= {e.baseline_capacity, e.retrofit_capacity}  # always needed downstream
    if capacities is None:
        qs.add(e.retrofit_capacity + 1)
    time = ctx.time_model(speed_kmh, stop_min)
    problems = [ctx.problem(Q, shift_hours, speed_kmh=speed_kmh, stop_min=stop_min) for Q in sorted(qs)]
    sols = ctx.sweep(problems)
    rows = []
    for Q, sol in sorted(sols.items()):
        stats = sol.balance_stats(time, ctx.overnight_min)
        rows.append({"capacity": Q, "shift_hours": shift_hours or 0.0,
                     "speed_kmh": time.speed_kmh, "stop_min": time.stop_min,
                     "method": sol.method, **stats})
    df = pd.DataFrame(rows)
    df["marginal_value_km"] = -df.total_km.diff()
    return df, sols


def breakeven_table(ctx: Context, sweep: pd.DataFrame, baseline_q: int) -> pd.DataFrame:
    e = ctx.settings.economics
    base_km = float(sweep.loc[sweep.capacity == baseline_q, "total_km"].iloc[0])
    rows = []
    for _, r in sweep.iterrows():
        saving_km = base_km - r.total_km
        row = {"capacity": int(r.capacity), "total_km": r.total_km, "saving_km_per_cycle": saving_km}
        for case in ("low", "mid", "high"):
            row[f"annual_saving_rs_{case}"] = saving_km * ctx.rate * ctx.cycles(case)
        for yrs in e.horizons_years:
            row[f"breakeven_capex_{yrs}y_mid"] = breakeven_capex(row["annual_saving_rs_mid"],
                                                                 e.discount_rate, yrs)
        row["payback_months_retrofit_mid"] = payback_months(e.retrofit_cost, row["annual_saving_rs_mid"])
        rows.append(row)
    return pd.DataFrame(rows)


def run(ctx: Context) -> None:
    ctx.log("== C2: capacity sweep (no duration limit) ==")
    e = ctx.settings.economics
    sweep, _ = capacity_sweep(ctx)
    ctx.save_table(sweep, "c2_capacity_sweep")
    be = breakeven_table(ctx, sweep, e.baseline_capacity)
    ctx.save_table(be, "c2_breakeven")

    retro = be[be.capacity.isin([e.retrofit_capacity, e.retrofit_capacity + 1])].copy()
    retro["retrofit_cost_rs"] = e.retrofit_cost
    retro["worth_it_1y_horizon"] = retro[f"breakeven_capex_{e.horizons_years[0]}y_mid"] >= e.retrofit_cost
    ctx.save_table(retro, "c2_retrofit_evaluation")

    r25 = be[be.capacity == e.retrofit_capacity].iloc[0]
    mv = sweep.set_index("capacity").marginal_value_km
    ctx.record("c2", c_q20_km=float(sweep.set_index("capacity").total_km[e.baseline_capacity]),
               c_q25_km=float(r25.total_km), retrofit_saving_km_per_cycle=float(r25.saving_km_per_cycle),
               retrofit_annual_saving_rs=dict(low=r25.annual_saving_rs_low, mid=r25.annual_saving_rs_mid,
                                              high=r25.annual_saving_rs_high),
               retrofit_payback_months_mid=float(r25.payback_months_retrofit_mid),
               retrofit_breakeven_capex_1y_mid=float(r25[f"breakeven_capex_{e.horizons_years[0]}y_mid"]),
               mean_mv_km_below_20=float(mv[mv.index <= e.baseline_capacity].mean()),
               mean_mv_km_above_20=float(mv[mv.index > e.baseline_capacity].mean()),
               c_qmax_km=float(sweep.total_km.iloc[-1]))
    _plot(ctx, sweep, be)


def _plot(ctx: Context, sweep: pd.DataFrame, be: pd.DataFrame) -> None:
    e = ctx.settings.economics
    fig, ax = plotting.plt.subplots(figsize=(6.2, 3.8))
    ax.plot(sweep.capacity, sweep.total_km, "o-", color=plotting.PALETTE[0], label="C(Q), best found")
    ax.set_xlabel("Truck capacity Q (cryocans)")
    ax.set_ylabel("km per delivery cycle")
    ax2 = ax.twinx()
    ax2.bar(sweep.capacity, sweep.marginal_value_km.fillna(0), alpha=0.25,
            color=plotting.PALETTE[2], label="Marginal value C(Q-1) - C(Q)")
    ax2.set_ylabel("Marginal value (km per cycle)")
    ax2.grid(False)
    for q in (e.baseline_capacity, e.retrofit_capacity):
        ax.axvline(q, color=plotting.GREY, ls=":", lw=1)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right")
    ax.set_title("Cost curve C(Q) and the marginal value of capacity (no time limit)")
    plotting.save(fig, ctx.figure_path("c2_cost_curve"))

    fig, ax = plotting.plt.subplots(figsize=(6.2, 3.8))
    sub = be[be.capacity >= e.baseline_capacity]
    for k, yrs in enumerate(e.horizons_years):
        ax.plot(sub.capacity, sub[f"breakeven_capex_{yrs}y_mid"] / 1000, "o-",
                color=plotting.PALETTE[k], label=f"{yrs}-year horizon")
    lo = sub.annual_saving_rs_low / 1000
    hi = sub.annual_saving_rs_high / 1000
    ax.fill_between(sub.capacity, lo, hi, color=plotting.PALETTE[0], alpha=0.12,
                    label="1-year saving, seasonal range")
    ax.scatter([e.retrofit_capacity], [e.retrofit_cost / 1000], marker="*", s=180,
               color=plotting.PALETTE[1], zorder=5, label="Actual retrofit (Rs 20,000)")
    ax.set_xlabel("Capacity after upgrade, Q (from Q = 20)")
    ax.set_ylabel("Maximum worthwhile one-time cost (Rs '000)")
    ax.set_title("Break-even curve: willingness to pay for capacity")
    ax.legend(fontsize=8)
    plotting.save(fig, ctx.figure_path("c2_breakeven_curve"))
