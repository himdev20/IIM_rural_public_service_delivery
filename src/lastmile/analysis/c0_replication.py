"""Component 0 -- benchmark and solver.

1. Rebuild the status quo (Table 1) and the spreadsheet savings model, and check
   that the numbers match exactly: 2,602 km (reported) / 2,336.7 km (Q=20) /
   2,237.5 km (Q=25). Route-by-route identity with the workbook's solution
   sheets is asserted, not just the totals.
2. Compare solvers (spreadsheet CW, clean CW, CW + 2-opt, OR-Tools) at Q=20/25.
3. Convergence: OR-Tools at increasing time limits, to show the "best" solver
   result is stable enough that later capacity effects are not search noise.
"""

from __future__ import annotations

import pandas as pd

from .. import plotting
from ..data import load_spreadsheet_solution, load_spreadsheet_sort, load_status_quo
from ..model import Problem, Solution
from ..solvers import solve_vba
from ..solvers.savings_vba import vba_sorted_pairs
from .common import Context


class ReplicationError(AssertionError):
    pass


def status_quo_solution(ctx: Context, capacity: int | None = None) -> Solution:
    """Table 1 routes as a Solution. Capacity defaults to the largest route load
    (the status quo over-fills the truck on long routes)."""
    routes = load_status_quo(ctx.settings.path(ctx.settings.data.case_workbook))
    seqs = [list(r.sequence) for r in routes]
    cap = capacity or max(len(s) for s in seqs)
    return Solution(Problem(ctx.instance, cap), seqs, method="status_quo",
                    meta={"names": [r.name for r in routes],
                          "reported_km": [r.reported_km for r in routes]})


def replicate(ctx: Context) -> dict:
    s = ctx.settings
    case_wb = s.path(s.data.case_workbook)
    model_wb = s.path(s.data.spreadsheet_model)
    if s.data.distance_mode != "raw":
        raise ReplicationError("Replication requires distance_mode = 'raw'")

    # --- status quo -------------------------------------------------------
    sq = status_quo_solution(ctx)
    sq_rows = []
    for name, rep, km, seq, dur in zip(sq.meta["names"], sq.meta["reported_km"], sq.route_km,
                                       sq.routes, sq.durations_min(ctx.base_time)):
        sq_rows.append({"route": name, "locations": len(seq), "reported_km": rep,
                        "matrix_km": km, "difference_km": km - rep,
                        "duration_h_base": dur / 60, "over_capacity_by": max(0, len(seq) - 20)})
    sq_table = pd.DataFrame(sq_rows)
    ctx.save_table(sq_table, "c0_status_quo_routes")
    reported_total = float(sq_table.reported_km.sum())

    # --- spreadsheet sort order -------------------------------------------
    stored = load_spreadsheet_sort(model_wb)
    ours = vba_sorted_pairs(ctx.instance)
    sort_mismatches = sum(a != b for a, b in zip(stored, ours)) + abs(len(stored) - len(ours))

    # --- spreadsheet savings solutions ------------------------------------
    rows = [{"benchmark": "Status quo (Table 1, reported)", "target_km": 2602.0,
             "python_km": reported_total, "routes_identical": None},
            {"benchmark": "Status quo (Table 1, re-measured on matrix)", "target_km": None,
             "python_km": sq.total_km, "routes_identical": None}]
    checks = {"status_quo_reported": abs(reported_total - 2602.0) < 1e-9,
              "sort_order": sort_mismatches == 0}
    for Q, sheet, target in ((20, "Sheet20", 2336.7), (25, "Sheet25", 2237.5)):
        sheet_sol = load_spreadsheet_solution(model_wb, sheet)
        sol = solve_vba(Problem(ctx.instance, Q))
        identical = [list(r) for r in sol.routes] == sheet_sol["routes"]
        rows.append({"benchmark": f"Spreadsheet savings model, Q={Q} ({sheet})",
                     "target_km": target, "python_km": round(sol.total_km, 4),
                     "routes_identical": identical})
        checks[f"Q{Q}_total"] = abs(sol.total_km - target) < 1e-6
        checks[f"Q{Q}_routes"] = identical
        checks[f"Q{Q}_sheet_total"] = abs(sheet_sol["total_km"] - target) < 1e-6
    table = pd.DataFrame(rows)
    table["match"] = [abs(a - b) < 1e-6 if pd.notna(a) else None
                      for a, b in zip(table.target_km, table.python_km)]
    ctx.save_table(table, "c0_replication", float_fmt="%.4f")

    if not all(checks.values()):
        raise ReplicationError(f"Replication failed: {checks}")
    ctx.log("  replication OK: 2602 / 2336.7 / 2237.5 km reproduced; routes identical")
    ctx.record("c0", status_quo_reported_km=reported_total, status_quo_matrix_km=sq.total_km,
               spreadsheet_q20_km=2336.7, spreadsheet_q25_km=2237.5,
               sort_pairs_checked=len(stored), replication_checks=checks,
               triangle_violation_share=ctx.instance.triangle_violation_share())
    return checks


def compare_solvers(ctx: Context, capacities=(20, 25)) -> pd.DataFrame:
    rows = []
    for Q in capacities:
        p = Problem(ctx.instance, Q)
        sols = [ctx.engine.run(p, m) for m in ("cw_spreadsheet", "cw", "cw2opt", "ortools")]
        best = ctx.engine.best(p, equal_effort=False)  # best known solution
        for sol in sols + [best]:
            label = "best found" if sol is best else sol.method
            rows.append({"capacity": Q, "method": label, "total_km": sol.total_km,
                         "routes": sol.n_routes, "max_load": max(sol.loads),
                         "seconds": sol.meta.get("seconds"), "feasible": sol.is_feasible})
    df = pd.DataFrame(rows)
    base = df[df.method == "cw_spreadsheet"].set_index("capacity").total_km
    df["vs_spreadsheet_pct"] = [100 * (km / base[q] - 1) for q, km in zip(df.capacity, df.total_km)]
    ctx.save_table(df, "c0_solver_comparison")
    best = df[df.method == "best found"].set_index("capacity").total_km
    ctx.record("c0", best_q20_km=best.get(20), best_q25_km=best.get(25))
    return df


def convergence(ctx: Context, capacities=(20, 25)) -> pd.DataFrame:
    """OR-Tools (cold start) objective vs time limit at Q=20 and Q=25.

    Also reports the retrofit value C(20) - C(25) at each *matched* search effort:
    if it moved a lot with effort, capacity conclusions would be solver artefacts.
    """
    rows = []
    for Q in capacities:
        p = Problem(ctx.instance, Q)
        for tl in ctx.settings.solver.convergence_time_limits_s:
            sol = ctx.engine.run(p, "ortools", time_limit_s=tl)
            rows.append({"capacity": Q, "time_limit_s": tl, "total_km": sol.total_km, "routes": sol.n_routes})
            ctx.log(f"  convergence Q={Q} t={tl}s -> {sol.total_km:.1f}")
    df = pd.DataFrame(rows)
    ctx.save_table(df, "c0_convergence")

    piv = df.pivot(index="time_limit_s", columns="capacity", values="total_km")
    lo, hi = min(capacities), max(capacities)
    effort = pd.DataFrame({"time_limit_s": piv.index, f"c_q{lo}_km": piv[lo].values,
                           f"c_q{hi}_km": piv[hi].values,
                           "retrofit_saving_km": (piv[lo] - piv[hi]).values,
                           f"c_q{lo}_running_best": piv[lo].cummin().values,
                           f"c_q{hi}_running_best": piv[hi].cummin().values})
    effort["retrofit_saving_running_best_km"] = effort[f"c_q{lo}_running_best"] - effort[f"c_q{hi}_running_best"]
    ctx.save_table(effort, "c0_retrofit_value_vs_effort")

    fig, ax = plotting.plt.subplots(figsize=(5.8, 3.6))
    for k, Q in enumerate(capacities):
        g = df[df.capacity == Q]
        ax.plot(g.time_limit_s, g.total_km, "o-", color=plotting.PALETTE[k], label=f"OR-Tools, Q = {Q}")
    ax.axhline(2336.7, color=plotting.PALETTE[0], ls="--", lw=1, label="Spreadsheet, Q = 20")
    ax.axhline(2237.5, color=plotting.PALETTE[1], ls="--", lw=1, label="Spreadsheet, Q = 25")
    ax.set_xscale("log")
    ax.set_xlabel("OR-Tools time limit (s, log scale)")
    ax.set_ylabel("Total distance per cycle (km)")
    ax.set_title("Solver convergence")
    ax.legend(fontsize=8)
    plotting.save(fig, ctx.figure_path("c0_convergence"))
    ctx.record("c0", convergence_best_km={str(Q): float(df[df.capacity == Q].total_km.min()) for Q in capacities},
               convergence_spread_km={str(Q): float(df[df.capacity == Q].total_km.max()
                                                    - df[df.capacity == Q].total_km.min()) for Q in capacities},
               retrofit_km_by_effort=dict(zip(map(str, effort.time_limit_s),
                                              effort.retrofit_saving_running_best_km.round(1))))
    return df


def run(ctx: Context) -> None:
    ctx.log("== C0: replication and solver benchmark ==")
    replicate(ctx)
    compare_solvers(ctx)
    convergence(ctx)
