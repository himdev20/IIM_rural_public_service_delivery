"""Write ``results/SUMMARY.md``: headline numbers and a check of each hypothesis.

The verdict rules are stated next to each verdict so a reader can disagree
with the threshold rather than with a hidden judgement.
"""

from __future__ import annotations

from datetime import date

from .common import Context

DATA_LIMITS = """\
* **No travel times.** Durations use assumed speeds (35-45 km/h) and stop times (15-30 min).
* **One per-km rate** (Rs 19/km); no cost data for larger trucks, so capacity is valued by
  a break-even curve, not an "optimal" truck size.
* **Every location demands one cryocan** per visit; demand shocks are a stylised scenario.
* **One district** (Nagpur); statewide numbers are illustrative extrapolations.
* **The distance matrix is not metric**: {viol:.0%} of location pairs have a shorter path via a
  third location. All headline results use the matrix as supplied (needed for exact
  replication); C5 re-solves on the shortest-path closure.
* **Heuristic optimum.** "Best found" = best of Clarke-Wright, CW + 2-opt and OR-Tools (Guided
  Local Search, {tl:g} s per solve in this run) plus a pool of previously found feasible
  solutions; no optimality certificate. Convergence evidence: `c0_convergence.csv`, `c0_retrofit_value_vs_effort.csv`.
"""


def _fmt(x, nd=1, pct=False):
    if x is None:
        return "n/a"
    return f"{x:,.{nd}f}{'%' if pct else ''}"


def _verdict(ok) -> str:
    return {True: "**Supported**", False: "**Not supported**", None: "**Not evaluated**",
            "partial": "**Partially supported**"}[ok]


def build(ctx: Context) -> str:
    k = ctx.key_numbers()
    c0, c1, c2, c3, c4, c5 = (k.get(c, {}) for c in ("c0", "c1", "c2", "c3", "c4", "c5"))
    lines = [f"# Results summary ({ctx.settings.profile} profile, generated {date.today()})", ""]

    # ---------------------------------------------------------------- C0
    lines += ["## C0 Replication and solver benchmark", ""]
    if c0:
        lines += [
            f"* Status quo: reported **{_fmt(c0['status_quo_reported_km'])} km** (Table 1); "
            f"re-measured on the matrix {_fmt(c0['status_quo_matrix_km'])} km.",
            f"* Spreadsheet savings model reproduced exactly: **{_fmt(c0['spreadsheet_q20_km'])} km** (Q=20) "
            f"and **{_fmt(c0['spreadsheet_q25_km'])} km** (Q=25), route by route "
            f"({c0['sort_pairs_checked']:,} sorted savings pairs checked).",
            f"* Best known solution: {_fmt(c0.get('best_q20_km'))} km (Q=20), {_fmt(c0.get('best_q25_km'))} km (Q=25).",
            f"* Search-effort check: retrofit value C(20) - C(25) at matched OR-Tools budgets (s -> km): "
            f"{c0.get('retrofit_km_by_effort')}.", ""]

    # ---------------------------------------------------------------- H1
    lines += ["## H1 Judgment-based routing leaves a substantial efficiency gap", ""]
    h1 = None
    if c1:
        h1 = c1["nominal_total_gap_pct"] >= 5.0
        lines += [
            f"* Status quo {_fmt(c1['status_quo_km'])} km vs best {_fmt(c1['nominal_best_km'])} km at Q=20: "
            f"gap **{_fmt(c1['nominal_total_gap_km'])} km per cycle ({_fmt(c1['nominal_total_gap_pct'], pct=True)})**, "
            f"about Rs {_fmt(c1['nominal_gap_rs_per_year_mid'], 0)} per year (mid seasonal frequency).",
            f"* Decomposition: judgment vs. spreadsheet savings = {_fmt(100 * c1['nominal_judgment_share'], 0, True)} "
            f"of the gap; savings heuristic vs. best = {_fmt(100 * c1['nominal_heuristic_share'], 0, True)}.",
            f"* The status quo loads up to {c1['status_quo_max_load']} cryocans. At that matched capacity the "
            f"gap is {_fmt(c1['matched_total_gap_pct'], pct=True)}, so the gap is not an artefact of over-filling.",
            f"* Verdict: {_verdict(h1)} (rule: total gap >= 5% of status-quo km).", ""]

    # ---------------------------------------------------------------- H2
    lines += ["## H2 Diminishing marginal value of capacity, collapsing once same-day return binds", ""]
    h2 = None
    if c2 and c3:
        diminishing = c2["mean_mv_km_above_20"] < c2["mean_mv_km_below_20"]
        unl, head = c3["retrofit_saving_km_unlimited"], c3["retrofit_saving_km_headline"]
        collapse = unl > 0 and head <= 0.25 * unl
        h2 = diminishing and collapse
        lines += [
            f"* No time limit: mean marginal value {_fmt(c2['mean_mv_km_below_20'])} km/cycle per slot for "
            f"Q <= 20 vs {_fmt(c2['mean_mv_km_above_20'])} km for Q > 20. Capacity saturates at "
            f"Q = {c3['saturation_q_unlimited']}.",
            f"* Retrofit Q20 -> Q25 saves {_fmt(unl)} km/cycle without a time limit, "
            f"payback {_fmt(c2['retrofit_payback_months_mid'])} months (mid frequency); "
            f"under a {c3['headline_hours']:g}-hour limit it saves **{_fmt(head)} km/cycle**.",
            f"* Saturation capacity by limit: {c3['saturation_by_limit']}.",
            f"* Price of same-day return (Q=20, {c3['headline_hours']:g} h): "
            f"**{_fmt(c3['price_same_day_km_q20'])} km/cycle ({_fmt(c3['price_same_day_pct_q20'], pct=True)})**, "
            f"Rs {_fmt(c3['price_same_day_rs_year_mid_q20'], 0)} per year. Unconstrained Q=20 routes need "
            f"{c3['unlimited_q20_overnight_routes']} overnight stays (longest {_fmt(c3['unlimited_q20_max_duration_h'])} h).",
            f"* Sensitivity (speed x stop time): price of same-day return "
            f"{_fmt(c3.get('sens_price_same_day_pct_range', [None])[0], 0)}-"
            f"{_fmt(c3.get('sens_price_same_day_pct_range', [None, None])[1], 0)}%; retrofit value "
            f"{_fmt(c3.get('sens_retrofit_km_range', [None])[0])}-"
            f"{_fmt(c3.get('sens_retrofit_km_range', [None, None])[1])} km/cycle.",
            f"* Calibration: at {ctx.settings.time.speed_kmh:g} km/h, the case statement that only routes 3 and 9 "
            f"stay overnight implies stops of {_fmt(c3['calib_min_stop_min_at_base_speed_10h'])}-"
            f"{_fmt(c3['calib_max_stop_min_at_base_speed_10h'])} min with a 10-h day "
            f"(an empty or inverted range means the narrative and the assumed ranges cannot both hold).",
            f"* Verdict: {_verdict(h2)} (rules: mean marginal value above Q=20 below that at or under 20; "
            f"retrofit value under the headline limit <= 25% of its unconstrained value).", ""]

    # ---------------------------------------------------------------- H3
    lines += ["## H3 Costs concentrate in remote villages, and constraint changes hit them hardest", ""]
    h3 = None
    if c4:
        conc = c4["shapley_top20_remote_share"] > 0.2 and c4["shapley_spearman_rho"] > 0
        # Use the Shapley allocation for shifts: unlike marginal costs, it sums to total cost,
        # so a change in it is a genuine reallocation of the bill.
        shifts = {name.split(":")[0]: v for name, v in c4.get("shifts", {}).items()
                  if name.endswith("shapley_km") and v["q5_share_abs_change"] is not None
                  and v["q5_share_abs_change"] == v["q5_share_abs_change"]}  # drop NaN (no change)
        disprop = {name: v["q5_share_abs_change"] > 0.2 and (v["rho"] or 0) > 0 for name, v in shifts.items()}
        if conc and disprop and all(disprop.values()):
            h3 = True
        elif conc and any(disprop.values()):
            h3 = "partial"
        else:
            h3 = False
        shift_txt = "; ".join(
            f"{name}: {100 * v['q5_share_abs_change']:.0f}% of the reallocation, rho = {v['rho']:.2f}"
            for name, v in shifts.items())
        unchanged = [name.split(":")[0] for name, v in c4.get("shifts", {}).items()
                     if name.endswith("shapley_km") and name.split(":")[0] not in shifts]
        lines += [
            f"* Scenario {c4['base_scenario']}: the 20% most remote villages carry "
            f"**{_fmt(100 * c4['shapley_top20_remote_share'], 0, True)}** of route cost (Shapley) and "
            f"{_fmt(100 * c4['mc_top20_remote_share'], 0, True)} of summed marginal costs; Spearman rho with distance "
            f"= {_fmt(c4['shapley_spearman_rho'], 2)} (Shapley), {_fmt(c4['mc_spearman_rho'], 2)} (marginal).",
            f"* Reallocation of the Shapley bill falling on the most remote quintile: {shift_txt}."
            + (f" No change at all for: {', '.join(unchanged)} (identical routes)." if unchanged else ""),
            f"* Verdict: {_verdict(h3)} (rules: the most remote 20% bear > 20% of cost with positive rank "
            f"correlation; a change is 'disproportionate' if > 20% of the absolute reallocation falls on the "
            f"most remote quintile and the change rises with distance; partial = some but not all changes).", ""]

    # ---------------------------------------------------------------- C5
    if c5:
        lines += ["## C5 Robustness", ""]
        cyc = c5.get("cycles_per_year", {})
        pay = c5.get("retrofit_payback_months_unlimited", {})
        opt = c5.get("optimisation_saving_rs_year", {})
        lines += [
            f"* Delivery cycles per year: {_fmt(cyc.get('low'))}-{_fmt(cyc.get('high'))}.",
            f"* Annual saving from optimised routing (Q=20, no limit): Rs {_fmt(opt.get('low'), 0)}-"
            f"{_fmt(opt.get('high'), 0)}.",
            f"* Retrofit payback without a time limit: {_fmt(pay.get('high'))}-{_fmt(pay.get('low'))} months.",
        ]
        mc = c5.get("metric_closure", {})
        if mc:
            raw, clo = mc.get("raw matrix", {}), mc.get("shortest-path closure", {})
            lines += [f"* Shortest-path matrix: status-quo gap {_fmt(clo.get('gap_pct'), pct=True)} "
                      f"(raw: {_fmt(raw.get('gap_pct'), pct=True)}); retrofit value "
                      f"{_fmt(clo.get('retrofit_saving_km'))} km/cycle (raw: {_fmt(raw.get('retrofit_saving_km'))})."]
        lines += [""]

    lines += ["## Data limits", "", DATA_LIMITS.format(
        viol=c0.get("triangle_violation_share", float("nan")),
        tl=ctx.settings.solver.ortools_time_limit_s)]
    lines += ["All tables are in `tables/`, figures in `figures/`; see the README for the file map."]
    text = "\n".join(lines) + "\n"
    (ctx.out / "SUMMARY.md").write_text(text)
    return text


def run(ctx: Context) -> None:
    ctx.log("== Writing SUMMARY.md ==")
    build(ctx)
