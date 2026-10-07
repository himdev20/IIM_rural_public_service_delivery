"""Using the library directly (outside the CLI pipeline).

    python scripts/example_usage.py
"""

from lastmile.allocation import shapley_allocation
from lastmile.config import REPO_ROOT
from lastmile.data import load_case_instance
from lastmile.model import Problem, TimeModel
from lastmile.solvers import RoutingEngine, solve_vba

inst = load_case_instance(REPO_ROOT / "data/raw/02_Main_Case_Data_File.xlsx")

# 1. The spreadsheet's own algorithm, replicated exactly
print(solve_vba(Problem(inst, 20)).summary())

# 2. Best solution with a 10-hour same-day-return rule (40 km/h, 20 min per stop)
engine = RoutingEngine(ortools_time_limit_s=5)
problem = Problem(inst, capacity=25, time=TimeModel(speed_kmh=40, stop_min=20), max_duration_min=600)
best = engine.best(problem)
print(best.summary())
print(best.balance_stats())

# 3. Who pays: exact Shapley share of each village within its route
shares = shapley_allocation(best)
top = sorted(shares.items(), key=lambda kv: -kv[1])[:5]
for node, km in top:
    print(f"{inst.labels[node]:<25} {inst.depot_dist[node]:6.1f} km from lab, Shapley share {km:6.1f} km")
