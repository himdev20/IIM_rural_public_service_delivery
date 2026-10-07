"""Solver facade.

``RoutingEngine.best(problem)`` returns the cheapest feasible solution among:

1. Clarke-Wright savings;
2. Clarke-Wright + 2-opt;
3. OR-Tools (Guided Local Search, cold start);
4. a *pool* of previously found solutions for the same instance and customer
   set that are also feasible for this problem.

``RoutingEngine.sweep(problems)`` solves a family of problems that differ only in
capacity (a cost curve C(Q)) with a **continuation** scheme:

* up-pass  : Q ascending; OR-Tools is warm-started from the best solution at Q-1
             (always feasible at Q);
* down-pass: Q descending; the best solution at Q+1 is *repaired* to fit Q and
             OR-Tools is warm-started from it.

Each Q therefore receives the same search procedure and shares information with
its neighbours, so differences along the curve reflect capacity rather than the
luck of independent heuristic runs. Monotonicity (C non-increasing in Q, and in
the time limit) is guaranteed by the pool.

**Equal effort.** Pool entries remember the OR-Tools budget that produced them.
By default ``best`` ignores entries found with a larger budget than the sweep
budget (e.g. the 120-s convergence runs in C0), so no capacity level gets more
search than another. ``best(..., equal_effort=False)`` returns the best solution
known regardless of effort (used for the headline gap in C1).

Solutions are cached on disk (JSON lines) keyed by problem and method tag.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from ..model import Problem, Solution, best_of
from .ortools_vrp import solve_ortools
from .repair import repair
from .savings import clarke_wright
from .savings_vba import solve_vba
from .two_opt import two_opt

__all__ = ["RoutingEngine", "SolutionCache", "clarke_wright", "two_opt", "solve_ortools",
           "solve_vba", "repair"]


class SolutionCache:
    """Append-only JSON-lines store of routes keyed by (problem key, method tag)."""

    def __init__(self, path: Path | None):
        self.path = path
        self._data: dict[tuple[str, str], dict] = {}
        if path is not None and path.exists():
            with open(path) as fh:
                for line in fh:
                    if line.strip():
                        rec = json.loads(line)
                        self._data[(rec["problem"], rec["tag"])] = rec

    def records(self) -> list[dict]:
        return list(self._data.values())

    def get(self, problem: Problem, tag: str) -> Solution | None:
        rec = self._data.get((problem.key(), tag))
        if rec is None:
            return None
        return Solution(problem, rec["routes"], rec["method"], rec.get("meta", {}))

    def put(self, problem: Problem, tag: str, sol: Solution) -> None:
        rec = {"problem": problem.key(), "tag": tag, "describe": problem.describe(),
               "inst": problem.instance.fingerprint(), "full": problem.customers is None,
               **sol.to_dict()}
        self._data[(rec["problem"], tag)] = rec
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a") as fh:
                fh.write(json.dumps(rec) + "\n")


def _effort(meta: dict) -> float:
    """Search budget (s) behind a solution; heuristics count as zero."""
    return float(meta.get("effort_s", meta.get("time_limit_s", 0.0)) or 0.0)


class RoutingEngine:
    """Runs the solver portfolio with caching, a feasible-solution pool and sweeps."""

    def __init__(self, ortools_time_limit_s: float = 15, first_solution: str = "SAVINGS",
                 cache: SolutionCache | None = None, verbose: bool = True,
                 continuation_time_limit_s: float | None = None):
        self.time_limit = ortools_time_limit_s
        self.continuation_time_limit = (ortools_time_limit_s if continuation_time_limit_s is None
                                        else continuation_time_limit_s)
        self.first_solution = first_solution
        self.cache = cache or SolutionCache(None)
        self.verbose = verbose
        self._pool: dict[tuple, list[tuple[str, float, list[list[int]]]]] = defaultdict(list)
        self._seen: set[tuple] = set()
        for rec in self.cache.records():  # pre-load full-instance solutions from earlier runs
            if rec.get("full"):
                self._add((rec["inst"], None), rec["method"], _effort(rec.get("meta", {})), rec["routes"])

    @classmethod
    def from_settings(cls, settings, verbose: bool = True) -> "RoutingEngine":
        s = settings.solver
        cache = SolutionCache(settings.path(s.cache_file) if s.use_cache else None)
        return cls(s.ortools_time_limit_s, s.ortools_first_solution, cache, verbose,
                   getattr(s, "continuation_time_limit_s", None))

    @property
    def effort_cap(self) -> float:
        """Largest per-solve budget used in sweeps; pool entries above it are 'extra effort'."""
        return max(self.time_limit, self.continuation_time_limit)

    # ---------------------------------------------------------------- methods
    def run(self, problem: Problem, method: str, time_limit_s: float | None = None) -> Solution | None:
        """Run one method (cached). method in {cw, cw2opt, ortools, cw_spreadsheet}."""
        tl = self.time_limit if time_limit_s is None else time_limit_s
        tag = f"ortools[{tl:g}s,{self.first_solution}]" if method == "ortools" else method
        cached = self.cache.get(problem, tag)
        if cached is not None:
            self._remember(cached)
            return cached
        t0 = time.perf_counter()
        if method == "cw":
            sol = clarke_wright(problem)
        elif method == "cw2opt":
            sol = two_opt(clarke_wright(problem))
            sol.method = "cw+2opt"
        elif method == "ortools":
            sol = solve_ortools(problem, tl, self.first_solution)
        elif method == "cw_spreadsheet":
            sol = solve_vba(problem)
        else:
            raise ValueError(f"unknown method {method!r}")
        if sol is None:
            return None
        sol.meta.setdefault("seconds", round(time.perf_counter() - t0, 2))
        self._store(problem, tag, sol)
        return sol

    def warm(self, problem: Problem, start: Solution, tag: str,
             time_limit_s: float | None = None) -> Solution | None:
        """OR-Tools warm-started from `start` (cached under `tag`)."""
        cached = self.cache.get(problem, tag)
        if cached is not None:
            self._remember(cached)
            return cached
        tl = self.continuation_time_limit if time_limit_s is None else time_limit_s
        sol = solve_ortools(problem, tl, self.first_solution, initial_routes=start.routes)
        if sol is None:
            return None
        sol.meta["effort_s"] = tl
        sol.method = tag.split("[")[0]
        self._store(problem, tag, sol)
        return sol

    def best(self, problem: Problem, methods: tuple[str, ...] = ("cw", "cw2opt", "ortools"),
             equal_effort: bool = True, quiet: bool = False,
             time_limit_s: float | None = None, continuation_s: float | None = None) -> Solution:
        """Cheapest feasible solution from the portfolio and the pool."""
        tl = self.time_limit if time_limit_s is None else time_limit_s
        cont = self.continuation_time_limit if continuation_s is None else continuation_s
        candidates = [self.run(problem, m, tl) for m in methods]
        candidates += self.pool_candidates(problem, max(tl, cont) if equal_effort else None)
        best = best_of(candidates)
        best = Solution(problem, best.routes, best.method, dict(best.meta))
        if self.verbose and not quiet:
            print(f"  [{problem.describe()}] best={best.total_km:8.1f} km via {best.method}", flush=True)
        return best

    def sweep(self, problems: list[Problem], time_limit_s: float | None = None,
              continuation_s: float | None = None) -> dict[int, Solution]:
        """Continuation sweep over problems that differ only in capacity."""
        tl = self.time_limit if time_limit_s is None else time_limit_s
        cont = self.continuation_time_limit if continuation_s is None else continuation_s
        problems = sorted(problems, key=lambda p: p.capacity)
        sols: dict[int, Solution] = {}
        for k, p in enumerate(problems):                       # up-pass
            sols[p.capacity] = self.best(p, quiet=True, time_limit_s=tl, continuation_s=cont)
            if k > 0:
                prev = sols[problems[k - 1].capacity].rebind(p)
                up = self.warm(p, prev, f"ortools-up[{cont:g}s]", cont)
                sols[p.capacity] = best_of([s for s in (sols[p.capacity], up) if s is not None])
        for k in range(len(problems) - 2, -1, -1):              # down-pass
            p = problems[k]
            start = repair(sols[problems[k + 1].capacity], p)
            if start is not None:
                down = self.warm(p, start, f"ortools-down[{cont:g}s]", cont)
                sols[p.capacity] = best_of([s for s in (sols[p.capacity], start, down) if s is not None])
                self._remember(sols[p.capacity])
        return {p.capacity: self.best(p, time_limit_s=tl, continuation_s=cont)  # monotone envelope
                for p in problems}

    # ------------------------------------------------------------------ pool
    @staticmethod
    def _pool_key(problem: Problem) -> tuple:
        return (problem.instance.fingerprint(), problem.customers)

    def _store(self, problem: Problem, tag: str, sol: Solution) -> None:
        if sol.is_feasible:
            self.cache.put(problem, tag, sol)
            self._remember(sol)

    def _remember(self, sol: Solution) -> None:
        self._add(self._pool_key(sol.problem), sol.method, _effort(sol.meta), sol.routes)

    def _add(self, key: tuple, method: str, effort: float, routes: list[list[int]]) -> None:
        signature = (key, tuple(sorted(tuple(r) for r in routes)))
        if signature in self._seen:
            return
        self._seen.add(signature)
        self._pool[key].append((method, effort, [list(r) for r in routes]))

    def pool_candidates(self, problem: Problem, max_effort: float | None = None) -> list[Solution]:
        out = []
        for method, effort, routes in self._pool[self._pool_key(problem)]:
            if max_effort is not None and effort > max_effort + 1e-9:
                continue
            cand = Solution(problem, routes, f"pool:{method}")
            if cand.is_feasible:
                out.append(cand)
        return out

    def add_to_pool(self, sol: Solution) -> None:
        self._remember(sol)
