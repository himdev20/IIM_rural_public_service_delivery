# Results summary (quick profile, generated 2026-10-07)

## C0 Replication and solver benchmark

* Status quo: reported **2,602.0 km** (Table 1); re-measured on the matrix 2,600.5 km.
* Spreadsheet savings model reproduced exactly: **2,336.7 km** (Q=20) and **2,237.5 km** (Q=25), route by route (15,576 sorted savings pairs checked).
* Best known solution: 2,206.0 km (Q=20), 2,054.2 km (Q=25).
* Search-effort check: retrofit value C(20) - C(25) at matched OR-Tools budgets (s -> km): {'120': 178.1, '15': 150.0, '30': 122.3, '5': 107.5, '60': 137.1}.

## H1 Judgment-based routing leaves a substantial efficiency gap

* Status quo 2,600.5 km vs best 2,206.0 km at Q=20: gap **394.5 km per cycle (15.2%)**, about Rs 100,344 per year (mid seasonal frequency).
* Decomposition: judgment vs. spreadsheet savings = 67% of the gap; savings heuristic vs. best = 33%.
* The status quo loads up to 28 cryocans. At that matched capacity the gap is 23.1%, so the gap is not an artefact of over-filling.
* Verdict: **Supported** (rule: total gap >= 5% of status-quo km).

## H2 Diminishing marginal value of capacity, collapsing once same-day return binds

* No time limit: mean marginal value 64.7 km/cycle per slot for Q <= 20 vs 21.2 km for Q > 20. Capacity saturates at Q = 29.
* Retrofit Q20 -> Q25 saves 140.5 km/cycle without a time limit, payback 6.7 months (mid frequency); under a 10-hour limit it saves **0.0 km/cycle**.
* Saturation capacity by limit: {'10 h': 16, '12 h': 17, '8 h': 15, 'no limit': 29}.
* Price of same-day return (Q=20, 10 h): **329.5 km/cycle (14.9%)**, Rs 83,811 per year. Unconstrained Q=20 routes need 8 overnight stays (longest 14.3 h).
* Sensitivity (speed x stop time): price of same-day return 3-44%; retrofit value 0.0-0.0 km/cycle.
* Calibration: at 40 km/h, the case statement that only routes 3 and 9 stay overnight implies stops of 0.0-3.3 min with a 10-h day (an empty or inverted range means the narrative and the assumed ranges cannot both hold).
* Verdict: **Supported** (rules: mean marginal value above Q=20 below that at or under 20; retrofit value under the headline limit <= 25% of its unconstrained value).

## H3 Costs concentrate in remote villages, and constraint changes hit them hardest

* Scenario Q20_none: the 20% most remote villages carry **33%** of route cost (Shapley) and 35% of summed marginal costs; Spearman rho with distance = 0.72 (Shapley), 0.24 (marginal).
* Reallocation of the Shapley bill falling on the most remote quintile: Q20_none->Q20_10h: 34% of the reallocation, rho = 0.51; Q20_none->Q25_none: 13% of the reallocation, rho = 0.09; Q25_none->Q25_10h: 40% of the reallocation, rho = 0.44. No change at all for: Q20_10h->Q25_10h (identical routes).
* Verdict: **Partially supported** (rules: the most remote 20% bear > 20% of cost with positive rank correlation; a change is 'disproportionate' if > 20% of the absolute reallocation falls on the most remote quintile and the change rises with distance; partial = some but not all changes).

## C5 Robustness

* Delivery cycles per year: 12.5-14.4.
* Annual saving from optimised routing (Q=20, no limit): Rs 93,844-107,822.
* Retrofit payback without a time limit: 6.2-7.2 months.
* Shortest-path matrix: status-quo gap 11.4% (raw: 15.2%); retrofit value 151.0 km/cycle (raw: 140.5).

## Data limits

* **No travel times.** Durations use assumed speeds (35-45 km/h) and stop times (15-30 min).
* **One per-km rate** (Rs 19/km); no cost data for larger trucks, so capacity is valued by
  a break-even curve, not an "optimal" truck size.
* **Every location demands one cryocan** per visit; demand shocks are a stylised scenario.
* **One district** (Nagpur); statewide numbers are illustrative extrapolations.
* **The distance matrix is not metric**: 58% of location pairs have a shorter path via a
  third location. All headline results use the matrix as supplied (needed for exact
  replication); C5 re-solves on the shortest-path closure.
* **Heuristic optimum.** "Best found" = best of Clarke-Wright, CW + 2-opt and OR-Tools (Guided
  Local Search, 15 s per solve in this run) plus a pool of previously found feasible
  solutions; no optimality certificate. Convergence evidence: `c0_convergence.csv`, `c0_retrofit_value_vs_effort.csv`.

All tables are in `tables/`, figures in `figures/`; see the README for the file map.
