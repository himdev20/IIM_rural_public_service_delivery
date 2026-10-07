"""Component 5 -- robustness and policy counterfactuals.

1. Seasonality: visit intervals (22-25 days summer, 30-35 winter) -> annual
   savings and payback of the retrofit, with and without a same-day-return rule.
2. Per-km rate and diesel-price sensitivity.
3. STYLISED demand shock: a random share of locations needs two cryocans per
   visit in summer. Clearly labelled as illustrative; there are no such data.
4. Distance-matrix robustness: shortest-path (metric) closure of the matrix.
5. Rough statewide extrapolation to the other districts (heavily caveated).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import plotting
from ..economics import breakeven_capex, payback_months, rate_after_fuel_shock
from ..model import route_distance
from .c0_replication import status_quo_solution
from .common import Context, shift_label


def _best_km(ctx: Context, Q: int, H: float | None, instance=None) -> float:
    return ctx.best(ctx.problem(Q, H, instance=instance)).total_km


def seasonality_payback(ctx: Context) -> pd.DataFrame:
    e, t = ctx.settings.economics, ctx.settings.time
    sq_km = status_quo_solution(ctx).total_km
    rows = []
    for H in [None] + sorted(t.shift_hours):
        c20 = _best_km(ctx, e.baseline_capacity, H)
        c25 = _best_km(ctx, e.retrofit_capacity, H)
        for case, cycles in ctx.seasonality.cycles_range().items():
            retro = (c20 - c25) * ctx.rate * cycles
            rows.append({
                "shift_limit": shift_label(H), "season_case": case, "cycles_per_year": cycles,
                "status_quo_rs_year": sq_km * ctx.rate * cycles,
                "best_q20_rs_year": c20 * ctx.rate * cycles,
                "optimisation_saving_rs_year": (sq_km - c20) * ctx.rate * cycles,
                "retrofit_saving_km_cycle": c20 - c25,
                "retrofit_saving_rs_year": retro,
                "retrofit_payback_months": payback_months(e.retrofit_cost, retro),
                "retrofit_npv_1y": breakeven_capex(retro, e.discount_rate, 1) - e.retrofit_cost,
            })
    df = pd.DataFrame(rows)
    ctx.save_table(df, "c5_seasonality_payback")
    unl = df[df.shift_limit == "no limit"].set_index("season_case")
    ctx.record("c5", cycles_per_year=ctx.seasonality.cycles_range(),
               optimisation_saving_rs_year={k: float(v) for k, v in unl.optimisation_saving_rs_year.items()},
               retrofit_payback_months_unlimited={k: float(v) for k, v in unl.retrofit_payback_months.items()})
    return df


def rate_fuel_sensitivity(ctx: Context) -> pd.DataFrame:
    e, t = ctx.settings.economics, ctx.settings.time
    sq_km = status_quo_solution(ctx).total_km
    rows = []
    for H in (None, t.headline_shift_hours):
        c20 = _best_km(ctx, e.baseline_capacity, H)
        c25 = _best_km(ctx, e.retrofit_capacity, H)
        rates = [("rate", r, r) for r in e.rate_grid]
        rates += [("fuel shock", s, rate_after_fuel_shock(e.rate_per_km, e.fuel_share_of_rate, s))
                  for s in e.fuel_shocks]
        for kind, param, rate in rates:
            for case in ("low", "mid", "high"):
                cyc = ctx.cycles(case)
                retro = (c20 - c25) * rate * cyc
                rows.append({"shift_limit": shift_label(H), "scenario": kind, "parameter": param,
                             "rate_per_km": rate, "season_case": case,
                             "optimisation_saving_rs_year": (sq_km - c20) * rate * cyc,
                             "retrofit_saving_rs_year": retro,
                             "retrofit_payback_months": payback_months(e.retrofit_cost, retro)})
    df = pd.DataFrame(rows)
    ctx.save_table(df, "c5_rate_fuel_sensitivity")

    fig, ax = plotting.plt.subplots(figsize=(6, 3.6))
    for k, (lim, g) in enumerate(df[(df.scenario == "rate") & (df.season_case == "mid")].groupby("shift_limit")):
        ax.plot(g.rate_per_km, g.retrofit_payback_months.replace(np.inf, np.nan), "o-",
                color=plotting.PALETTE[k], label=f"Duration limit: {lim}")
        lo = df[(df.scenario == "rate") & (df.season_case == "high") & (df.shift_limit == lim)]
        hi = df[(df.scenario == "rate") & (df.season_case == "low") & (df.shift_limit == lim)]
        ax.fill_between(lo.rate_per_km, lo.retrofit_payback_months.replace(np.inf, np.nan),
                        hi.retrofit_payback_months.replace(np.inf, np.nan), color=plotting.PALETTE[k], alpha=0.12)
    ax.axhline(12, color=plotting.GREY, ls="--", lw=1, label="One-year truck contract")
    ax.axvline(e.rate_per_km, color=plotting.GREY, ls=":", lw=1)
    ax.set_xlabel("Hire rate (Rs per km)")
    ax.set_ylabel("Payback of Rs 20,000 retrofit (months)")
    ax.set_title("Retrofit payback: rate and seasonal-frequency sensitivity")
    ax.legend(fontsize=8)
    plotting.save(fig, ctx.figure_path("c5_retrofit_payback"))
    return df


def demand_shock(ctx: Context) -> pd.DataFrame:
    """STYLISED: a random fraction of locations needs 2 cryocans in summer."""
    r, e, t = ctx.settings.robustness, ctx.settings.economics, ctx.settings.time
    rng = np.random.default_rng(r.seed)
    base = ctx.instance
    rows = []
    for frac in r.demand_shock_fractions:
        for draw in range(r.demand_shock_draws):
            demand = base.demand.copy()
            pick = rng.choice(base.customers, size=int(round(frac * base.n)), replace=False)
            demand[pick] = 2
            inst = base.with_demand(demand, name=f"shock{frac:g}-{draw}")
            for H in (None, t.headline_shift_hours):
                kms = {Q: _best_km(ctx, Q, H, instance=inst) for Q in r.demand_shock_capacities}
                for Q, km in kms.items():
                    rows.append({"label": "STYLISED demand shock", "fraction_double": frac, "draw": draw,
                                 "shift_limit": shift_label(H), "capacity": Q, "total_km": km,
                                 "total_demand": int(demand.sum())})
    df = pd.DataFrame(rows)
    # baseline (no shock) for comparison
    base_rows = [{"label": "baseline", "fraction_double": 0.0, "draw": 0, "shift_limit": shift_label(H),
                  "capacity": Q, "total_km": _best_km(ctx, Q, H), "total_demand": int(base.demand.sum())}
                 for H in (None, t.headline_shift_hours) for Q in r.demand_shock_capacities]
    df = pd.concat([pd.DataFrame(base_rows), df], ignore_index=True)
    ctx.save_table(df, "c5_demand_shock_runs")

    q_lo, q_hi = min(r.demand_shock_capacities), max(r.demand_shock_capacities)
    piv = df.pivot_table(index=["fraction_double", "draw", "shift_limit"], columns="capacity",
                         values="total_km").reset_index()
    piv["retrofit_saving_km_cycle"] = piv[q_lo] - piv[q_hi]
    summ = piv.groupby(["fraction_double", "shift_limit"]).agg(
        retrofit_saving_km_mean=("retrofit_saving_km_cycle", "mean"),
        retrofit_saving_km_min=("retrofit_saving_km_cycle", "min"),
        retrofit_saving_km_max=("retrofit_saving_km_cycle", "max"),
        cost_q20_km_mean=(q_lo, "mean")).reset_index()
    s = ctx.seasonality
    summer_cycles = s.summer_days / np.mean(s.summer_interval)
    winter_cycles = s.winter_days / np.mean(s.winter_interval)
    base_saving = summ[summ.fraction_double == 0].set_index("shift_limit").retrofit_saving_km_mean
    summ["annual_retrofit_saving_rs_summer_shock"] = [
        (row.retrofit_saving_km_mean * summer_cycles + base_saving[row.shift_limit] * winter_cycles) * ctx.rate
        for row in summ.itertuples()]
    summ["label"] = np.where(summ.fraction_double > 0, "STYLISED demand shock (summer only)", "baseline")
    ctx.save_table(summ, "c5_demand_shock_summary")
    ctx.record("c5", demand_shock_retrofit_km={f"{r.fraction_double:g}|{r.shift_limit}": float(r.retrofit_saving_km_mean)
                                               for r in summ.itertuples()})
    return summ


def metric_closure(ctx: Context) -> pd.DataFrame:
    e = ctx.settings.economics
    closed = ctx.instance.metric_closure()
    sq = status_quo_solution(ctx)
    rows = []
    for label, inst in (("raw matrix", ctx.instance), ("shortest-path closure", closed)):
        sq_km = sum(route_distance(inst, r) for r in sq.routes)
        c20 = _best_km(ctx, e.baseline_capacity, None, instance=inst)
        c25 = _best_km(ctx, e.retrofit_capacity, None, instance=inst)
        rows.append({"matrix": label, "status_quo_km": sq_km, "best_q20_km": c20, "best_q25_km": c25,
                     "gap_pct": 100 * (sq_km - c20) / sq_km, "retrofit_saving_km": c20 - c25})
    df = pd.DataFrame(rows)
    df["triangle_violation_share"] = [ctx.instance.triangle_violation_share(), 0.0]
    ctx.save_table(df, "c5_metric_closure")
    ctx.record("c5", metric_closure=df.set_index("matrix").to_dict(orient="index"))
    return df


def extrapolation(ctx: Context) -> pd.DataFrame:
    """Back-of-envelope statewide range. Assumes other districts resemble Nagpur
    up to a scale factor -- an assumption the data cannot test."""
    x, e = ctx.settings.extrapolation, ctx.settings.economics
    sq_km = status_quo_solution(ctx).total_km
    c20 = _best_km(ctx, e.baseline_capacity, None)
    c20_h = _best_km(ctx, e.baseline_capacity, ctx.settings.time.headline_shift_hours)
    rows = []
    for label, km in (("optimised routes, no time limit", c20), ("optimised routes, same-day return", c20_h)):
        for case in ("low", "mid", "high"):
            nagpur = (sq_km - km) * ctx.rate * ctx.cycles(case)
            rows.append({"policy": label, "season_case": case, "nagpur_rs_year": nagpur,
                         "other_districts": x.other_districts,
                         "statewide_low_rs_year": nagpur * x.other_districts * x.scale_low,
                         "statewide_high_rs_year": nagpur * x.other_districts * x.scale_high,
                         "caveat": "illustrative only: one district of data"})
    df = pd.DataFrame(rows)
    ctx.save_table(df, "c5_extrapolation")
    return df


def run(ctx: Context) -> None:
    ctx.log("== C5: robustness and counterfactuals ==")
    seasonality_payback(ctx)
    rate_fuel_sensitivity(ctx)
    demand_shock(ctx)
    metric_closure(ctx)
    extrapolation(ctx)
