# Methodology

Research question: *how do vehicle capacity and working-time constraints jointly determine the
cost of delivering a public service across dispersed rural locations, and where does that cost
fall?*

Story: judgment-based routing → optimisation benchmark → capacity and time constraints → cost
structure and who bears it → policy counterfactuals.

## The model

* **Network.** Node 0 is the Frozen Serum Laboratory (FSL, Nagpur); nodes 1-177 are livestock
  locations. Distances (km) come from the case workbook; the matrix is symmetric.
* **Demand.** One 50-litre cryocan per location per visit (stylised shocks in C5 use two).
* **Vehicle.** One hired truck, paid Rs 19 per km. Each *route* is one trip; routes are run one
  after another, so the number of routes is not a fleet-size decision. Capacity Q = 20 cryocans
  (Q = 25-26 after the Rs 20,000 partition retrofit).
* **Cost.** Total km per *delivery cycle* (every location visited once) × rate × cycles per year.
* **Time (Component 3 only).** Route duration = km / speed + stops × stop time (+ optional depot
  time and extra minutes per additional cryocan). A same-day-return rule caps the duration at H
  hours (8 a.m. to 6 p.m. = 10 h).

## Component 0 — benchmark and solver

* Exact replication of the spreadsheet (see `replication_notes.md`).
* Solver portfolio:
  * **Clarke-Wright savings** (`solvers/savings.py`), parallel version with capacity and duration
    checks at every merge.
  * **CW + 2-opt** (`solvers/two_opt.py`), best-improvement 2-opt within each route.
  * **OR-Tools** (`solvers/ortools_vrp.py`): savings first solution, then Guided Local Search for a
    fixed time budget. Capacity is a dimension; duration is a time dimension whose arc times are
    rounded *up* so every accepted route is feasible in exact arithmetic.
* **"Best found"** = cheapest feasible solution among the three **plus a pool** of every feasible
  solution found earlier for the same instance (`RoutingEngine.best`). A solution feasible at Q is
  feasible at Q+1, and a solution feasible under an 8-h limit is feasible under 10 h, so cost
  curves are guaranteed monotone; heuristic noise cannot masquerade as negative value of capacity.
* **Convergence check:** OR-Tools at 5-120 s (5-600 s in the `full` profile) at Q = 20.

Warm-starting OR-Tools from the spreadsheet solution was tested and found to get stuck in a worse
local optimum than a cold start, so cold starts plus the pool are used.

## Component 1 — the cost of rules of thumb

Total gap = (status quo − savings heuristic) + (savings heuristic − best). Reported:

* **nominal**: heuristic and best at Q = 20;
* **capacity-matched**: at Q = 28, the largest load the status quo actually puts on the truck
  (several current routes over-fill it). This isolates routing judgment from the extra capacity
  the status quo borrows.

## Component 2 — capacity–cost trade-off

* C(Q) for Q = 15…30 without a time limit; marginal value MV(Q) = C(Q−1) − C(Q).
* **Break-even curve**: the maximum one-time payment worth making to move from Q = 20 to Q:
  PV of (C(20) − C(Q)) × rate × cycles/yr over 1, 3 and 5 years at 8 %. The truck is hired on a
  yearly contract, so the 1-year horizon is the conservative one.
* The Rs 20,000 retrofit (Q = 25, and 26) is evaluated against it: savings, payback, 1-year NPV.

## Component 3 — the time constraint (headline)

* C(Q) for Q = 15…30 under H ∈ {8, 9, 10, 12 h, unlimited} at 40 km/h and 20 min/stop.
* **Saturation capacity** Q\*(H): the smallest Q whose cost is within max(1 km, 0.25 %) of the cost
  at Q = 30 — beyond Q\*, extra capacity is worth (almost) nothing.
* **Price of same-day return** C_H(Q) − C_∞(Q), in km and Rs per year: the cost of a
  worker-welfare constraint.
* **Efficiency vs balanced service**: number of routes, max/min/CV of route km, longest duration,
  overnight routes, truck-days per cycle (status quo vs best, with and without the limit).
* **Sensitivity**: speeds {35, 40, 45} × stop times {15, 20, 30} at H = 10 h.
* **Calibration check**: for each speed, the range of stop times under which *only* routes 3 and 9
  exceed the working day (the case narrative). An empty or tiny range means the narrative and the
  assumed ranges are hard to reconcile — reported, not hidden.

## Component 4 — who bears the cost

For scenarios (Q, H) ∈ {20, 25} × {unlimited, 10 h}:

* **Marginal cost** MC_i = C(N) − C(N∖i), with C(N∖i) the best of: dropping i and 2-opting its
  route; OR-Tools warm-started from that for a few seconds; and *driving through* i's location
  without stopping. The last option matters because the matrix is not metric — skipping a stop can
  make the direct link longer — and it guarantees MC_i ≥ 0. This is a local re-optimisation
  marginal cost, i.e. what a planner would save by dropping one village.
* **Shapley share** within each route, computed **exactly** with a closed form for the fixed-order
  route game (`allocation.py`; verified against brute force in the tests). It sums to the route
  length, so changes in it are genuine reallocations of the bill.
* Outputs: per-village table; cost shares by remoteness quintile; top-20 % remote share; Gini;
  Spearman correlation with distance; and shifts in allocation when only capacity or only the time
  limit changes.

## Component 5 — robustness and counterfactuals

* **Seasonality**: 12.5-14.4 cycles per year (22-25-day summer and 30-35-day winter intervals)
  feeding annual savings and payback.
* **Per-km rate and diesel price**: rate grid Rs 15-25; fuel shocks −20 % to +40 % applied to an
  assumed 60 % fuel share of the hire rate.
* **Stylised demand shock** (labelled as such): 10 % or 25 % of locations need two cryocans in
  summer; three random draws each.
* **Metric closure**: re-solve on shortest-path distances.
* **Extrapolation** to 35 other districts at 0.5-1.5 × Nagpur's savings — explicitly illustrative.

## Reproducibility

* All assumptions: `config/default.toml` (tagged [D] data or [A] assumption).
* Profiles: `smoke` (seconds), `quick` (committed results), `full` (recommended for the paper).
* Every solve is cached in `results/cache/solutions.jsonl`; deleting it forces re-solving.
* OR-Tools with a time limit is not bit-for-bit deterministic across machines; cached solutions
  make the committed numbers reproducible, and the convergence table shows how much they could
  move with more search.
