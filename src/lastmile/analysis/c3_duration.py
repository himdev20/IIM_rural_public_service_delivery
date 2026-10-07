"""Component 3 -- the time constraint (headline result).

Adds a route-duration limit (e.g. depart 8 a.m., return by 6 p.m. = 10 h) to the
capacity sweep. Travel times do not exist in the data, so durations come from
assumed speeds (35-45 km/h) and stop times (15-30 min), treated as ranges.

Outputs
* headline figure: one C(Q) curve per time limit, showing where extra capacity
  stops being worth anything (the "saturation capacity" Q*(H));
* price of the same-day-return rule: C_H(Q) - C_unlimited(Q), a worker-welfare
  constraint priced in km and rupees;
* efficiency vs balanced service: route-length balance and overnight stays;
* sensitivity of all of the above to speed and stop time;
* a calibration check against the case narrative ("only routes 3 and 9 cannot
  return the same day").
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import plotting
from .c0_replication import status_quo_solution
from .c2_capacity import capacity_sweep
from .common import Context, shift_label

OVERNIGHT_IN_CASE = ("Kuhi", "Mansar")  # routes 3 and 9, per the case text


# ---------------------------------------------------------------------------
# Calibration: which (speed, stop time) pairs reproduce the case narrative?
# ---------------------------------------------------------------------------
def calibration(ctx: Context) -> pd.DataFrame:
    sq = status_quo_solution(ctx)
    names = sq.meta["names"]
    rows = []
    for H in (10.0, 12.0):
        for v in (30, 35, 40, 45, 50, 55, 60):
            lo, hi = 0.0, np.inf
            for name, km, route in zip(names, sq.route_km, sq.routes):
                slack = (H * 60 - km / v * 60) / len(route)  # stop minutes that exactly fill the day
                if name in OVERNIGHT_IN_CASE:
                    lo = max(lo, slack)
                else:
                    hi = min(hi, slack)
            rows.append({"day_hours": H, "speed_kmh": v,
                         "min_stop_min": lo, "max_stop_min": hi,
                         "consistent": bool(hi > lo and hi > 0)})
    df = pd.DataFrame(rows)
    ctx.save_table(df, "c3_calibration_implied_stop_time")

    t = ctx.settings.time
    grid = []
    for v in t.speeds_kmh:
        for s in t.stops_min:
            durs = sq.durations_min(ctx.time_model(v, s))
            over = [n for n, d in zip(names, durs) if d > ctx.overnight_min]
            grid.append({"speed_kmh": v, "stop_min": s, "overnight_routes": len(over),
                         "overnight_names": ", ".join(over)})
    grid = pd.DataFrame(grid)
    ctx.save_table(grid, "c3_status_quo_overnight_by_assumption")
    base10 = df[(df.day_hours == 10.0) & (df.speed_kmh == int(t.speed_kmh))].iloc[0]
    ctx.record("c3", calib_max_stop_min_at_base_speed_10h=float(base10.max_stop_min),
               calib_min_stop_min_at_base_speed_10h=float(base10.min_stop_min),
               sq_overnight_routes_base=int(grid[(grid.speed_kmh == t.speed_kmh) &
                                                 (grid.stop_min == t.stop_min)].overnight_routes.iloc[0]))
    return df


# ---------------------------------------------------------------------------
# Headline: cost curves by time limit
# ---------------------------------------------------------------------------
def saturation_capacity(curve: pd.Series, tol_km: float = 1.0, tol_pct: float = 0.25) -> int:
    """Smallest Q whose cost is within tolerance of the cost at the largest Q."""
    floor = curve.iloc[-1]
    tol = max(tol_km, tol_pct / 100 * floor)
    return int(curve[curve - floor <= tol].index.min())


def headline(ctx: Context) -> pd.DataFrame:
    t = ctx.settings.time
    frames = []
    for H in sorted(t.shift_hours):  # tight first: their solutions seed looser limits
        ctx.log(f"-- duration limit {H:g} h (base speed/stop)")
        df, _ = capacity_sweep(ctx, H)
        frames.append(df)
    ctx.log("-- no duration limit")
    unl, _ = capacity_sweep(ctx, None)
    frames.append(unl)
    curves = pd.concat(frames, ignore_index=True)

    unl_km = unl.set_index("capacity").total_km
    curves["price_same_day_km"] = [km - unl_km[q] if h else 0.0
                                   for q, h, km in zip(curves.capacity, curves.shift_hours, curves.total_km)]
    curves["price_same_day_rs_year_mid"] = curves.price_same_day_km * ctx.rate * ctx.cycles("mid")
    ctx.save_table(curves, "c3_cost_curves_by_time_limit")

    e = ctx.settings.economics
    summary = []
    for H, g in curves.groupby("shift_hours"):
        c = g.set_index("capacity").total_km
        retro_km = c[e.baseline_capacity] - c[e.retrofit_capacity]
        summary.append({
            "shift_hours": H, "label": shift_label(H),
            "c_q20_km": c[e.baseline_capacity], "c_q25_km": c[e.retrofit_capacity],
            "retrofit_saving_km": retro_km,
            "retrofit_saving_rs_year_mid": retro_km * ctx.rate * ctx.cycles("mid"),
            "saturation_capacity": saturation_capacity(c),
            "price_same_day_km_q20": c[e.baseline_capacity] - unl_km[e.baseline_capacity],
            "routes_q20": int(g.set_index("capacity").n_routes[e.baseline_capacity]),
            "max_load_q20": int(g.set_index("capacity").max_load[e.baseline_capacity]),
        })
    summary = pd.DataFrame(summary)
    summary["price_same_day_rs_year_mid_q20"] = summary.price_same_day_km_q20 * ctx.rate * ctx.cycles("mid")
    ctx.save_table(summary, "c3_time_limit_summary")

    head = summary[summary.shift_hours == t.headline_shift_hours].iloc[0]
    none = summary[summary.shift_hours == 0].iloc[0]
    ctx.record("c3", headline_hours=t.headline_shift_hours,
               price_same_day_km_q20=float(head.price_same_day_km_q20),
               price_same_day_pct_q20=float(100 * head.price_same_day_km_q20 / none.c_q20_km),
               price_same_day_rs_year_mid_q20=float(head.price_same_day_rs_year_mid_q20),
               retrofit_saving_km_unlimited=float(none.retrofit_saving_km),
               retrofit_saving_km_headline=float(head.retrofit_saving_km),
               saturation_q_unlimited=int(none.saturation_capacity),
               saturation_q_headline=int(head.saturation_capacity),
               saturation_by_limit={shift_label(h): int(q) for h, q in
                                    zip(summary.shift_hours, summary.saturation_capacity)},
               unlimited_q20_overnight_routes=int(unl.set_index("capacity").overnight_routes[e.baseline_capacity]),
               unlimited_q20_max_duration_h=float(unl.set_index("capacity").max_duration_h[e.baseline_capacity]))
    _plot_headline(ctx, curves, summary)
    return curves


def _plot_headline(ctx: Context, curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    e = ctx.settings.economics
    t = ctx.settings.time
    fig, ax = plotting.plt.subplots(figsize=(7, 4.3))
    order = [0.0] + sorted(h for h in curves.shift_hours.unique() if h)[::-1]
    for k, H in enumerate(order):
        g = curves[curves.shift_hours == H].sort_values("capacity")
        q_star = int(summary.set_index("shift_hours").saturation_capacity[H])
        line, = ax.plot(g.capacity, g.total_km, "o-", ms=3.5, lw=1.8,
                        color="black" if H == 0 else plotting.PALETTE[k % len(plotting.PALETTE)],
                        label=f"{shift_label(H)} (capacity saturates at Q={q_star})")
        y = float(g.set_index("capacity").total_km[q_star])
        ax.plot([q_star], [y], marker="D", ms=7, mfc="white", mec=line.get_color(), zorder=5)
    for q in (e.baseline_capacity, e.retrofit_capacity):
        ax.axvline(q, color=plotting.GREY, ls=":", lw=1)
    ax.set_xlabel("Truck capacity Q (cryocans)")
    ax.set_ylabel("km per delivery cycle (best found)")
    ax.set_title(f"Cost curves by route-duration limit  "
                 f"({t.speed_kmh:g} km/h, {t.stop_min:g} min per stop)")
    ax.legend(fontsize=8, title="Return-by limit", title_fontsize=8)
    plotting.save(fig, ctx.figure_path("c3_headline_cost_curves"))


# ---------------------------------------------------------------------------
# Sensitivity to speed and stop time
# ---------------------------------------------------------------------------
def sensitivity(ctx: Context) -> pd.DataFrame:
    t, e = ctx.settings.time, ctx.settings.economics
    H = t.headline_shift_hours
    qs = sorted(set(ctx.settings.capacity.sensitivity_grid) | {e.baseline_capacity, e.retrofit_capacity})
    unl, _ = capacity_sweep(ctx, None, capacities=qs)
    unl_km = unl.set_index("capacity").total_km
    rows = []
    for v in t.speeds_kmh:
        for s in t.stops_min:
            ctx.log(f"-- sensitivity {v:g} km/h, {s:g} min/stop, {H:g} h")
            df, _ = capacity_sweep(ctx, H, speed_kmh=v, stop_min=s, capacities=qs)
            c = df.set_index("capacity")
            rows.append({
                "speed_kmh": v, "stop_min": s, "shift_hours": H,
                "c_q20_km": c.total_km[e.baseline_capacity], "c_q25_km": c.total_km[e.retrofit_capacity],
                "price_same_day_km_q20": c.total_km[e.baseline_capacity] - unl_km[e.baseline_capacity],
                "retrofit_saving_km": c.total_km[e.baseline_capacity] - c.total_km[e.retrofit_capacity],
                "saturation_capacity": saturation_capacity(c.total_km),
                "routes_q20": int(c.n_routes[e.baseline_capacity]),
                "max_load_q20": int(c.max_load[e.baseline_capacity]),
            })
    df = pd.DataFrame(rows)
    df["price_same_day_pct_q20"] = 100 * df.price_same_day_km_q20 / unl_km[e.baseline_capacity]
    df["retrofit_saving_rs_year_mid"] = df.retrofit_saving_km * ctx.rate * ctx.cycles("mid")
    ctx.save_table(df, "c3_sensitivity_speed_stop")
    ctx.record("c3", sens_price_same_day_pct_range=[float(df.price_same_day_pct_q20.min()),
                                                    float(df.price_same_day_pct_q20.max())],
               sens_retrofit_km_range=[float(df.retrofit_saving_km.min()), float(df.retrofit_saving_km.max())],
               sens_saturation_range=[int(df.saturation_capacity.min()), int(df.saturation_capacity.max())])
    _plot_sensitivity(ctx, df)
    return df


def _plot_sensitivity(ctx: Context, df: pd.DataFrame) -> None:
    panels = [("price_same_day_pct_q20", "Price of same-day return\n(% of unlimited cost, Q=20)", "{:.0f}%"),
              ("retrofit_saving_km", "Retrofit value Q20 -> Q25\n(km per cycle)", "{:.0f}"),
              ("saturation_capacity", "Saturation capacity Q*", "{:.0f}")]
    fig, axes = plotting.plt.subplots(1, 3, figsize=(12, 3.6))
    for ax, (col, title, fmt) in zip(axes, panels):
        piv = df.pivot(index="stop_min", columns="speed_kmh", values=col).sort_index(ascending=False)
        im = ax.imshow(piv.to_numpy(float), cmap="viridis", aspect="auto")
        ax.set_xticks(range(piv.shape[1]), [f"{c:g}" for c in piv.columns])
        ax.set_yticks(range(piv.shape[0]), [f"{r:g}" for r in piv.index])
        ax.set_xlabel("Speed (km/h)")
        ax.set_ylabel("Stop time (min)")
        ax.set_title(title, fontsize=9.5)
        ax.grid(False)
        vals = piv.to_numpy(float)
        for i in range(vals.shape[0]):
            for j in range(vals.shape[1]):
                ax.text(j, i, fmt.format(vals[i, j]), ha="center", va="center",
                        color="white" if vals[i, j] < np.nanmean(vals) else "black", fontsize=9)
        fig.colorbar(im, ax=ax, shrink=0.8)
    fig.suptitle(f"Sensitivity to driving speed and stop time "
                 f"({ctx.settings.time.headline_shift_hours:g}-hour limit)", y=1.03)
    plotting.save(fig, ctx.figure_path("c3_sensitivity_heatmaps"))


# ---------------------------------------------------------------------------
# Efficiency versus balanced service
# ---------------------------------------------------------------------------
def balance(ctx: Context) -> pd.DataFrame:
    e, t = ctx.settings.economics, ctx.settings.time
    sq = status_quo_solution(ctx)
    cases = [("Status quo", sq)]
    for Q in (e.baseline_capacity, e.retrofit_capacity):
        for H in (None, t.headline_shift_hours):
            cases.append((f"Best, Q={Q}, {shift_label(H)}", ctx.best(ctx.problem(Q, H))))
    rows, dists = [], []
    for name, sol in cases:
        rows.append({"solution": name, **sol.balance_stats(ctx.base_time, ctx.overnight_min)})
        dists.append((name, sol.route_km, sol.durations_min(ctx.base_time)))
    df = pd.DataFrame(rows)
    ctx.save_table(df, "c3_route_balance")

    fig, axes = plotting.plt.subplots(1, 2, figsize=(11, 3.8))
    labels = [d[0].replace(", ", "\n") for d in dists]
    axes[0].boxplot([d[1] for d in dists], tick_labels=labels, showmeans=True)
    axes[0].set_ylabel("Route length (km)")
    axes[0].set_title("Route lengths")
    axes[1].boxplot([np.array(d[2]) / 60 for d in dists], tick_labels=labels, showmeans=True)
    axes[1].axhline(ctx.overnight_min / 60, color=plotting.PALETTE[1], ls="--",
                    label="Same-day return limit")
    axes[1].set_ylabel(f"Route duration (h) at {t.speed_kmh:g} km/h, {t.stop_min:g} min/stop")
    axes[1].set_title("Route durations")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.tick_params(axis="x", labelsize=7.5)
    plotting.save(fig, ctx.figure_path("c3_route_balance"))
    return df


def run(ctx: Context) -> None:
    ctx.log("== C3: duration-constrained routing ==")
    calibration(ctx)
    headline(ctx)
    sensitivity(ctx)
    balance(ctx)
