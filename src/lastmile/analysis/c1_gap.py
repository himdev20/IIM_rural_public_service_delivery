"""Component 1 -- the cost of rules of thumb.

Total gap  = Status quo - Best
           = (Status quo - Savings heuristic)   "judgment vs. a simple rule"
           + (Savings heuristic - Best)          "simple rule vs. optimisation"

Two comparisons are reported because the status quo over-fills the truck
(up to 28 cryocans on a 20-cryocan truck):

* nominal   -- heuristic and best solution at the official capacity Q = 20;
* matched   -- heuristic and best solution at the capacity the status quo
               actually uses (its largest route load), which isolates the
               routing judgment from the extra capacity it borrows.
"""

from __future__ import annotations

import pandas as pd

from .. import plotting
from ..model import Problem
from .c0_replication import status_quo_solution
from .common import Context


def decomposition(ctx: Context) -> pd.DataFrame:
    sq = status_quo_solution(ctx)
    sq_km = sq.total_km
    sq_cap = max(sq.loads)
    nominal = ctx.settings.economics.baseline_capacity
    cyc, rate = ctx.cycles("mid"), ctx.rate

    rows = []
    for label, Q in (("nominal", nominal), ("capacity-matched", sq_cap)):
        p = Problem(ctx.instance, Q)
        heur = {
            "spreadsheet CW": ctx.engine.run(p, "cw_spreadsheet") if Q in (20, 25) else None,
            "clean CW": ctx.engine.run(p, "cw"),
            "CW + 2-opt": ctx.engine.run(p, "cw2opt"),
        }
        best = ctx.engine.best(p, equal_effort=False)  # best known, any search effort
        for hname, h in heur.items():
            if h is None or not h.is_feasible:
                continue
            total = sq_km - best.total_km
            judgment = sq_km - h.total_km
            rows.append({
                "comparison": label, "capacity": Q, "heuristic": hname,
                "status_quo_km": sq_km, "heuristic_km": h.total_km, "best_km": best.total_km,
                "judgment_gap_km": judgment, "heuristic_gap_km": h.total_km - best.total_km,
                "total_gap_km": total,
                "judgment_share": judgment / total, "heuristic_share": 1 - judgment / total,
                "total_gap_pct_of_sq": 100 * total / sq_km,
                "total_gap_rs_per_year_mid": total * rate * cyc,
            })
    df = pd.DataFrame(rows)
    ctx.save_table(df, "c1_gap_decomposition", float_fmt="%.3f")

    main = df[(df.comparison == "nominal") & (df.heuristic == "spreadsheet CW")].iloc[0]
    matched = df[(df.comparison == "capacity-matched") & (df.heuristic == "clean CW")].iloc[0]
    ctx.record("c1", status_quo_km=sq_km, status_quo_max_load=sq_cap,
               nominal_best_km=main.best_km, nominal_total_gap_km=main.total_gap_km,
               nominal_total_gap_pct=main.total_gap_pct_of_sq,
               nominal_judgment_share=main.judgment_share,
               nominal_heuristic_share=main.heuristic_share,
               nominal_gap_rs_per_year_mid=main.total_gap_rs_per_year_mid,
               matched_capacity=sq_cap, matched_best_km=matched.best_km,
               matched_total_gap_pct=matched.total_gap_pct_of_sq,
               matched_judgment_share=matched.judgment_share)
    _plot(ctx, df)
    return df


def _plot(ctx: Context, df: pd.DataFrame) -> None:
    sel = df[df.heuristic.isin(["spreadsheet CW", "clean CW"])]
    sel = sel.drop_duplicates("comparison", keep="first")
    fig, axes = plotting.plt.subplots(1, len(sel), figsize=(4.6 * len(sel), 3.6), sharey=True)
    axes = list(axes) if len(sel) > 1 else [axes]
    for ax, (_, r) in zip(axes, sel.iterrows()):
        levels = [r.status_quo_km, r.heuristic_km, r.best_km]
        labels = ["Status quo\n(judgment)", f"Savings\n({r.heuristic})", "Best found"]
        ax.bar(labels, levels, color=[plotting.GREY, plotting.PALETTE[2], plotting.PALETTE[0]])
        for k, v in enumerate(levels):
            ax.text(k, v + 15, f"{v:,.0f}", ha="center")
        ax.annotate(f"-{r.judgment_gap_km:,.0f} km\n({100 * r.judgment_share:.0f}% of gap)",
                    xy=(0.5, (levels[0] + levels[1]) / 2), ha="center", fontsize=8.5)
        ax.annotate(f"-{r.heuristic_gap_km:,.0f} km\n({100 * r.heuristic_share:.0f}% of gap)",
                    xy=(1.5, (levels[1] + levels[2]) / 2), ha="center", fontsize=8.5)
        ax.set_ylim(min(levels) * 0.85, max(levels) * 1.06)
        ax.set_title(f"{r.comparison.capitalize()} (Q = {r.capacity})")
    axes[0].set_ylabel("km per delivery cycle")
    fig.suptitle("Where the status-quo gap comes from", y=1.02)
    plotting.save(fig, ctx.figure_path("c1_gap_decomposition"))


def run(ctx: Context) -> None:
    ctx.log("== C1: gap decomposition ==")
    decomposition(ctx)
