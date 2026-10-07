# Trucks, Time, and the Last Mile

**Capacity constraints and the cost of rural public-service delivery**

> *How do vehicle capacity and working-time constraints jointly determine the cost of delivering
> a public service across dispersed rural locations, and where does that cost fall?*

This repository re-analyses the liquid-nitrogen (LN₂) distribution problem of the Frozen Serum
Laboratory, Animal Husbandry Department, Nagpur (Choudhari & Chandra, *INFORMS Transactions on
Education* 23(1), 2022): one hired truck, 177 livestock locations, nine judgment-based routes,
Rs 19/km, a 20-cryocan truck and a possible Rs 20,000 retrofit to 25-26 cryocans.

The story: **judgment-based routing → optimisation benchmark → capacity and time constraints →
cost structure and who bears it → policy counterfactuals.**

<!-- RESULTS:START -->
<!-- RESULTS:END -->

## Quick start

```bash
pip install -e ".[dev]"          # Python >= 3.11
make test                        # fast tests (exact replication included), ~5 s
make smoke                       # whole pipeline in ~1 min -> results_smoke/
make all                         # quick profile -> results/ (~2 h on one core; cached after)
make all PROFILE=full            # longer searches, recommended for the final paper
python -m lastmile c3            # any single component: c0 c1 c2 c3 c4 c5 report
python -m lastmile solve --capacity 25 --shift-hours 10   # one ad-hoc solve
```

Every solve is cached in `results/cache/solutions.jsonl`, so re-running a component (or the
report) after the first run takes seconds. `make clean-cache` forces fresh searches.

## Hypotheses and how each is tested

| | Hypothesis | Evidence | Component |
|---|---|---|---|
| H1 | Judgment-based routing leaves a substantial efficiency gap. | Gap decomposition: status quo → savings heuristic → best found; nominal (Q=20) and capacity-matched (Q=28, what the status quo actually loads). | C0, C1 |
| H2 | The marginal value of capacity diminishes, and falls sharply once a same-day-return limit binds. | C(Q) curves for Q = 15-30 under each duration limit; marginal values; saturation capacity Q\*(H); break-even curve; retrofit evaluation. | C2, C3 |
| H3 | Service costs are concentrated in remote villages, so changes in capacity or time limits affect them disproportionately. | Village marginal costs and exact route-level Shapley shares vs distance from the lab; shifts across scenarios. | C4 |

`results/SUMMARY.md` states each verdict together with the rule used to reach it.

## Components

| | What | Main outputs (`results/`) |
|---|---|---|
| **C0** Benchmark & solver | Exact rebuild of the spreadsheet VBA model; solver comparison (spreadsheet CW, CW, CW+2-opt, OR-Tools); convergence and retrofit-value-vs-effort checks | `tables/c0_replication.csv`, `c0_status_quo_routes.csv`, `c0_solver_comparison.csv`, `c0_convergence.csv`, `c0_retrofit_value_vs_effort.csv`, `figures/c0_convergence.png` |
| **C1** Cost of rules of thumb | Gap = (judgment − heuristic) + (heuristic − best), nominal and capacity-matched | `tables/c1_gap_decomposition.csv`, `figures/c1_gap_decomposition.png` |
| **C2** Capacity–cost trade-off | C(Q), marginal value, break-even (willingness-to-pay) curve, Rs 20,000 retrofit | `tables/c2_capacity_sweep.csv`, `c2_breakeven.csv`, `c2_retrofit_evaluation.csv`, `figures/c2_cost_curve.png`, `c2_breakeven_curve.png` |
| **C3** Time constraint (headline) | C(Q) for each route-duration limit; saturation capacity; price of same-day return; balance & overnight stays; speed × stop sensitivity; calibration vs case narrative | `figures/c3_headline_cost_curves.png`, `c3_sensitivity_heatmaps.png`, `c3_route_balance.png`, `tables/c3_*.csv` |
| **C4** Who bears the cost | Village marginal costs, exact Shapley shares, concentration by remoteness, shifts across scenarios | `tables/c4_village_costs.csv`, `c4_incidence_summary.csv`, `c4_allocation_shifts.csv`, `figures/c4_*.png` |
| **C5** Robustness & counterfactuals | Seasonality → annual savings & payback; rate and diesel sensitivity; **stylised** demand shock; metric-closure matrix; statewide extrapolation (illustrative) | `tables/c5_*.csv`, `figures/c5_retrofit_payback.png` |

## Repository layout

```
config/default.toml        every assumption, tagged [D] data or [A] assumption; profiles quick/full/smoke
data/raw/                  case workbook, spreadsheet model (.xlsm), ABC teaching instance (tests)
docs/
  methodology.md           methods per component
  replication_notes.md     how the spreadsheet was reproduced, VBA quirks, data quirks
  data_limitations.md      the limits to state up front, and how each is handled
src/lastmile/
  data.py                  Instance (depot = node 0), loaders, savings matrix, metric closure
  model.py                 Problem (capacity, duration limit, customer subset), TimeModel, Solution
  solvers/
    savings_vba.py         line-by-line replica of the spreadsheet macro (exact replication)
    savings.py             clean Clarke-Wright with capacity + duration checks
    two_opt.py             intra-route 2-opt
    ortools_vrp.py         OR-Tools CVRP with optional duration dimension, warm starts
    repair.py              make a solution feasible for a tighter problem
    __init__.py            RoutingEngine: portfolio, cache, solution pool, continuation sweep
  allocation.py            exact route-level Shapley values, detour costs, concentration
  economics.py             seasonality, annualisation, break-even, payback, fuel shocks
  analysis/c0..c5, report  one module per component; report writes results/SUMMARY.md
  cli.py                   python -m lastmile ...
tests/                     replication, solvers, Shapley vs brute force, economics, config
scripts/example_usage.py   using the library directly
```

## Design choices worth knowing

* **Exact replication first.** `solvers/savings_vba.py` reproduces the workbook's routes node by
  node, including Excel's sort of five text-typed distance cells and an off-by-one in the macro
  (`docs/replication_notes.md`). Analyses then use a clean Clarke-Wright and stronger solvers.
* **Best found = portfolio + pool.** Any solution feasible at Q is feasible at Q+1 (and under a
  looser time limit), so the engine reuses every feasible solution it has seen. Cost curves are
  therefore monotone by construction.
* **Continuation sweeps with equal effort.** Single heuristic runs at 15 s vary by ±50 km at
  Q = 20 — as large as the per-slot effect being measured. Capacity curves are therefore solved
  with an up-pass (warm-start from Q−1) and a down-pass (repair Q+1, warm-start), and longer
  convergence runs are excluded from the curves so no capacity level receives extra search.
  `c0_retrofit_value_vs_effort.csv` shows how the retrofit value moves with search effort.
* **Marginal costs can't go negative.** The matrix is not metric; when a village is dropped the
  truck may still drive the old path, so MC ≥ 0 by construction.
* **Shapley without sampling.** For a route served in fixed order, the Shapley value has a closed
  form (sum over edges of unanimity-with-exclusion games); tests check it against brute force.

## Data limits (stated up front)

No travel times (speeds and stop times are assumed ranges); a single per-km rate; one cryocan per
location; one district; a non-metric distance matrix (58 % of pairs have a shorter path through a
third location); status-quo routes over-fill the truck. Details and how each is handled:
`docs/data_limitations.md`.

## Source

Choudhari, S., & Chandra, S. (2022). Route Planning at an Animal Husbandry Department.
*INFORMS Transactions on Education*, 23(1), 41-45. https://doi.org/10.1287/ited.2021.0250cs
(CC BY-SA 4.0). Distance data: "RPAHD Data Files" supplementary workbook.
