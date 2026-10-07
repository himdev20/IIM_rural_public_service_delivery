"""Shared plumbing for the analysis components (C0-C5)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import Settings
from ..data import Instance, load_case_instance
from ..economics import Seasonality
from ..model import Problem, TimeModel
from ..solvers import RoutingEngine


@dataclass
class Context:
    settings: Settings
    instance: Instance
    engine: RoutingEngine
    _key_numbers: dict = field(default_factory=dict)

    # ----------------------------------------------------------- construction
    @classmethod
    def build(cls, settings: Settings, verbose: bool = True) -> "Context":
        inst = load_case_instance(settings.path(settings.data.case_workbook))
        if settings.data.distance_mode == "metric":
            inst = inst.metric_closure()
        ctx = cls(settings, inst, RoutingEngine.from_settings(settings, verbose))
        for sub in ("tables", "figures"):
            (ctx.out / sub).mkdir(parents=True, exist_ok=True)
        return ctx

    # ------------------------------------------------------------- problems
    def time_model(self, speed_kmh: float | None = None, stop_min: float | None = None) -> TimeModel:
        t = self.settings.time
        return TimeModel(speed_kmh=speed_kmh or t.speed_kmh, stop_min=stop_min or t.stop_min,
                         depot_min=t.depot_min, extra_unit_min=t.extra_unit_min)

    def problem(self, capacity: int, shift_hours: float | None = None, *,
                speed_kmh: float | None = None, stop_min: float | None = None,
                instance: Instance | None = None) -> Problem:
        """Problem with an optional route-duration limit (hours; None/0 = unlimited)."""
        inst = instance or self.instance
        if not shift_hours:
            return Problem(inst, capacity)
        return Problem(inst, capacity, self.time_model(speed_kmh, stop_min), shift_hours * 60.0)

    def budgets(self, problem: Problem) -> tuple[float, float]:
        """(cold, continuation) OR-Tools budgets; duration-limited problems may use smaller ones."""
        s = self.settings.solver
        if problem.has_duration_limit:
            return (getattr(s, "constrained_time_limit_s", s.ortools_time_limit_s),
                    getattr(s, "constrained_continuation_s", s.continuation_time_limit_s))
        return s.ortools_time_limit_s, s.continuation_time_limit_s

    def best(self, problem: Problem, **kw):
        tl, cont = self.budgets(problem)
        return self.engine.best(problem, time_limit_s=tl, continuation_s=cont, **kw)

    def sweep(self, problems: list[Problem]):
        tl, cont = self.budgets(problems[0])
        return self.engine.sweep(problems, tl, cont)

    @property
    def base_time(self) -> TimeModel:
        return self.time_model()

    @property
    def overnight_min(self) -> float:
        return self.settings.time.overnight_threshold_hours * 60.0

    # ------------------------------------------------------------ economics
    @property
    def rate(self) -> float:
        return float(self.settings.economics.rate_per_km)

    @property
    def seasonality(self) -> Seasonality:
        return Seasonality.from_settings(self.settings.seasonality)

    def cycles(self, case: str = "mid") -> float:
        return self.seasonality.cycles_per_year(case)

    # --------------------------------------------------------------- outputs
    @property
    def out(self) -> Path:
        return self.settings.results_dir

    def save_table(self, df: pd.DataFrame, name: str, float_fmt: str = "%.2f") -> Path:
        path = self.out / "tables" / f"{name}.csv"
        df.to_csv(path, index=False, float_format=float_fmt)
        return path

    def figure_path(self, name: str) -> Path:
        return self.out / "figures" / f"{name}.png"

    def record(self, component: str, **numbers: Any) -> None:
        """Store headline numbers in results/key_numbers.json (merged across runs)."""
        path = self.out / "key_numbers.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        data.setdefault(component, {}).update(_jsonable(numbers))
        path.write_text(json.dumps(data, indent=2, sort_keys=True))

    def key_numbers(self) -> dict:
        path = self.out / "key_numbers.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def log(self, msg: str) -> None:
        if self.engine.verbose:
            print(msg, flush=True)


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    if isinstance(obj, float):
        return round(obj, 4)
    return obj


def shift_label(hours: float | None) -> str:
    return "no limit" if not hours else f"{hours:g} h"
