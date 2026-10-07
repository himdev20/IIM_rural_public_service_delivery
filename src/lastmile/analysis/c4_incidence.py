"""Component 4 -- who bears the cost?

For each scenario (capacity Q, duration limit H):

* **Marginal cost** MC_i = C(N) - C(N minus i). C(N minus i) is the best of
  (a) the incumbent with i dropped and its route re-optimised by 2-opt;
  (b) the incumbent with the truck still *driving through* i's location without
      stopping (the matrix is not metric, so dropping a stop can lengthen the
      direct link; driving the old path is always possible, so MC_i >= 0);
  (c) OR-Tools warm-started from (a) for ``marginal_resolve_s`` seconds.
  This is a *local* re-optimisation marginal cost: it holds most of the network
  fixed, which is also how a planner would actually drop a village.
* **Shapley share** -- exact route-level Shapley allocation (see allocation.py).
* **Stand-alone cost** 2 d(0, i) -- what a dedicated trip would cost.

Then: how do these relate to distance from the lab, how concentrated are they,
and how do they shift when capacity or the time limit changes?
"""

from __future__ import annotations

import hashlib
import itertools
import json

import numpy as np
import pandas as pd
from scipy import stats

from .. import plotting
from ..allocation import concentration, detour_cost, shapley_allocation
from ..model import Solution, best_of
from ..solvers import solve_ortools, two_opt
from .common import Context, shift_label


def _scenario_name(Q: int, H: float) -> str:
    return f"Q{Q}_{'none' if not H else f'{H:g}h'}"


def marginal_costs(ctx: Context, base: Solution) -> pd.DataFrame:
    p = base.problem
    budget = ctx.settings.solver.marginal_resolve_s
    detour = detour_cost(base)
    base_id = hashlib.sha1(json.dumps(sorted(base.routes)).encode()).hexdigest()[:10]
    rows = []
    for k, i in enumerate(p.nodes):
        without = p.without(i)
        tag = f"marginal[{budget:g}s,{base_id}]"  # tied to the base plan it starts from
        sol = ctx.engine.cache.get(without, tag)
        if sol is None:
            dropped = Solution(without, [[x for x in r if x != i] for r in base.routes], "drop")
            cands = [two_opt(dropped)]
            if budget > 0:
                cands.append(solve_ortools(without, budget, ctx.engine.first_solution,
                                           initial_routes=cands[0].routes))
            feasible = [c for c in cands if c is not None and c.is_feasible]
            sol = best_of(feasible) if feasible else None
            if sol is not None:
                ctx.engine.cache.put(without, tag, sol)
        reopt_km = sol.total_km if sol is not None else np.inf
        drive_through = base.total_km - max(detour[i], 0.0)
        c_without = min(reopt_km, drive_through)
        rows.append({"location": i, "c_without_km": c_without, "reopt_km": reopt_km,
                     "detour_km": detour[i], "marginal_cost_km": base.total_km - c_without})
        if (k + 1) % 25 == 0:
            ctx.log(f"    marginal costs: {k + 1}/{len(p.nodes)}")
    return pd.DataFrame(rows)


def village_table(ctx: Context) -> pd.DataFrame:
    inst = ctx.instance
    frames = []
    for sc in ctx.settings.incidence.scenarios:
        Q, H = int(sc.capacity), float(sc.shift_hours)
        name = _scenario_name(Q, H)
        ctx.log(f"-- incidence scenario {name}")
        base = ctx.best(ctx.problem(Q, H or None))
        mc = marginal_costs(ctx, base)
        shap = shapley_allocation(base)
        route_of = {i: k for k, r in enumerate(base.routes) for i in r}
        mc["scenario"] = name
        mc["capacity"], mc["shift_hours"] = Q, H
        mc["shapley_km"] = mc.location.map(shap)
        mc["route"] = mc.location.map(route_of)
        mc["total_km"] = base.total_km
        frames.append(mc)
    df = pd.concat(frames, ignore_index=True)
    df["name"] = df.location.map(lambda i: inst.labels[i])
    df["depot_km"] = df.location.map(lambda i: inst.depot_dist[i])
    df["standalone_km"] = 2 * df.depot_km
    q = ctx.settings.incidence.remote_quantiles
    df["remoteness_quintile"] = pd.qcut(df.depot_km.rank(method="first"), q, labels=range(1, q + 1)).astype(int)
    df["marginal_cost_rs_year_mid"] = df.marginal_cost_km * ctx.rate * ctx.cycles("mid")
    df["shapley_rs_year_mid"] = df.shapley_km * ctx.rate * ctx.cycles("mid")
    cols = ["scenario", "capacity", "shift_hours", "location", "name", "depot_km", "remoteness_quintile",
            "route", "marginal_cost_km", "shapley_km", "detour_km", "standalone_km",
            "marginal_cost_rs_year_mid", "shapley_rs_year_mid", "reopt_km", "c_without_km", "total_km"]
    df = df[cols]
    ctx.save_table(df, "c4_village_costs", float_fmt="%.3f")
    return df


def incidence_summary(ctx: Context, df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, g in df.groupby("scenario", sort=False):
        for measure in ("marginal_cost_km", "shapley_km"):
            conc = concentration(g[measure].to_numpy(), g.depot_km.to_numpy(), top_share=0.2)
            rho, pval = stats.spearmanr(g.depot_km, g[measure]) if g[measure].std() > 0 else (np.nan, np.nan)
            row = {"scenario": name, "measure": measure, "spearman_rho_vs_distance": rho,
                   "spearman_p": pval, "top20pct_remote_share": conc["top_share_of_cost"],
                   "gini": conc["gini"]}
            shares = g.groupby("remoteness_quintile")[measure].sum() / g[measure].sum()
            means = g.groupby("remoteness_quintile")[measure].mean()
            for qn in shares.index:
                row[f"share_q{qn}"] = shares[qn]
                row[f"mean_km_q{qn}"] = means[qn]
            rows.append(row)
    out = pd.DataFrame(rows)
    ctx.save_table(out, "c4_incidence_summary", float_fmt="%.4f")
    first = out[(out.scenario == out.scenario.iloc[0]) & (out.measure == "shapley_km")].iloc[0]
    first_mc = out[(out.scenario == out.scenario.iloc[0]) & (out.measure == "marginal_cost_km")].iloc[0]
    ctx.record("c4", base_scenario=str(first.scenario),
               shapley_top20_remote_share=float(first.top20pct_remote_share),
               shapley_spearman_rho=float(first.spearman_rho_vs_distance),
               mc_top20_remote_share=float(first_mc.top20pct_remote_share),
               mc_spearman_rho=float(first_mc.spearman_rho_vs_distance),
               mc_gini=float(first_mc.gini))
    return out


def shifts(ctx: Context, df: pd.DataFrame) -> pd.DataFrame:
    """Change in each village's allocation between pairs of scenarios."""
    wide = {m: df.pivot(index="location", columns="scenario", values=m) for m in ("shapley_km", "marginal_cost_km")}
    depot = df.drop_duplicates("location").set_index("location").depot_km
    quint = df.drop_duplicates("location").set_index("location").remoteness_quintile
    scen = list(dict.fromkeys(df.scenario))
    rows = []
    for a, b in itertools.combinations(scen, 2):
        qa, ha = df[df.scenario == a][["capacity", "shift_hours"]].iloc[0]
        qb, hb = df[df.scenario == b][["capacity", "shift_hours"]].iloc[0]
        if (qa != qb) + (ha != hb) != 1:
            continue  # only one-dimensional changes: capacity OR time limit
        for m, w in wide.items():
            delta = w[b] - w[a]
            if np.allclose(delta, 0):
                rho, p = np.nan, np.nan  # identical routes in both scenarios
            else:
                rho, p = stats.spearmanr(depot, delta)
            row = {"from": a, "to": b, "change": "capacity" if qa != qb else "time limit",
                   "measure": m, "total_change_km": delta.sum(), "spearman_rho_vs_distance": rho,
                   "spearman_p": p}
            by_q = delta.groupby(quint).mean()
            for qn in by_q.index:
                row[f"mean_change_km_q{qn}"] = by_q[qn]
            tot_abs = delta.abs().sum()
            row["remote_q5_share_of_abs_change"] = delta[quint == quint.max()].abs().sum() / tot_abs if tot_abs else np.nan
            rows.append(row)
    out = pd.DataFrame(rows)
    ctx.save_table(out, "c4_allocation_shifts", float_fmt="%.4f")
    if len(out):
        ctx.record("c4", shifts={f"{r['from']}->{r['to']}:{r['measure']}": {
            "rho": r["spearman_rho_vs_distance"], "q5_share_abs_change": r["remote_q5_share_of_abs_change"]}
            for _, r in out.iterrows()})
    return out


def _plots(ctx: Context, df: pd.DataFrame, summary: pd.DataFrame, shift_df: pd.DataFrame) -> None:
    scen = list(dict.fromkeys(df.scenario))
    fig, axes = plotting.plt.subplots(1, len(scen), figsize=(3.6 * len(scen), 3.4), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, s in zip(axes, scen):
        g = df[df.scenario == s]
        ax.scatter(g.depot_km, g.marginal_cost_km, s=10, alpha=0.6, label="Marginal cost")
        ax.scatter(g.depot_km, g.shapley_km, s=10, alpha=0.6, marker="x", label="Shapley share")
        Q, H = g.capacity.iloc[0], g.shift_hours.iloc[0]
        ax.set_title(f"Q={Q}, {shift_label(H)}", fontsize=9.5)
        ax.set_xlabel("Distance from lab (km)")
    axes[0].set_ylabel("km per delivery cycle")
    axes[0].legend(fontsize=8)
    fig.suptitle("Village-level cost versus remoteness", y=1.03)
    plotting.save(fig, ctx.figure_path("c4_cost_vs_distance"))

    fig, axes = plotting.plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, measure, title in ((axes[0], "shapley_km", "Shapley allocation"),
                               (axes[1], "marginal_cost_km", "Marginal cost")):
        sub = summary[summary.measure == measure]
        qcols = sorted(c for c in sub.columns if c.startswith("share_q"))
        x = np.arange(len(qcols))
        w = 0.8 / len(sub)
        for k, (_, r) in enumerate(sub.iterrows()):
            ax.bar(x + k * w, [100 * r[c] for c in qcols], w, label=r.scenario)
        ax.axhline(100 / len(qcols), color=plotting.GREY, ls="--", lw=1, label="Equal share")
        ax.set_xticks(x + w * (len(sub) - 1) / 2, [f"Q{c[-1]}" for c in qcols])
        ax.set_xlabel("Remoteness quintile (Q5 = farthest from lab)")
        ax.set_ylabel("% of total")
        ax.set_title(title)
    axes[0].legend(fontsize=7.5)
    plotting.save(fig, ctx.figure_path("c4_cost_share_by_remoteness"))

    if len(shift_df):
        sub = shift_df[shift_df.measure == "shapley_km"]
        qcols = sorted(c for c in sub.columns if c.startswith("mean_change_km_q"))
        fig, ax = plotting.plt.subplots(figsize=(6.4, 3.6))
        x = np.arange(len(qcols))
        w = 0.8 / max(len(sub), 1)
        for k, (_, r) in enumerate(sub.iterrows()):
            ax.bar(x + k * w, [r[c] for c in qcols], w, label=f"{r['from']} -> {r['to']}")
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(x + w * (len(sub) - 1) / 2, [f"Q{c[-1]}" for c in qcols])
        ax.set_xlabel("Remoteness quintile (Q5 = farthest)")
        ax.set_ylabel("Mean change in Shapley share (km/cycle)")
        ax.set_title("Who gains when capacity or the time limit changes?")
        ax.legend(fontsize=7.5)
        plotting.save(fig, ctx.figure_path("c4_allocation_shifts"))


def run(ctx: Context) -> None:
    ctx.log("== C4: who bears the cost ==")
    df = village_table(ctx)
    summary = incidence_summary(ctx, df)
    shift_df = shifts(ctx, df)
    _plots(ctx, df, summary, shift_df)
