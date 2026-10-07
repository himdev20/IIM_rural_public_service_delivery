"""Command-line interface.

    python -m lastmile all                 # every component, quick profile
    python -m lastmile c0 c1 --profile full
    python -m lastmile solve --capacity 25 --shift-hours 10
"""

from __future__ import annotations

import argparse
import time

from .analysis import COMPONENTS
from .analysis.common import Context
from .config import load_settings

ORDER = ["c0", "c1", "c2", "c3", "c4", "c5", "report"]


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="lastmile", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+", help=f"components to run: {', '.join(ORDER)}, all, or solve")
    ap.add_argument("--profile", default="quick", help="config profile: quick | full | smoke")
    ap.add_argument("--no-cache", action="store_true", help="ignore and do not write the solution cache")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--capacity", type=int, default=20, help="(solve) truck capacity")
    ap.add_argument("--shift-hours", type=float, default=0.0, help="(solve) route-duration limit; 0 = none")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = load_settings(args.profile)
    if args.no_cache:
        settings = settings.override("solver", use_cache=False)
    ctx = Context.build(settings, verbose=not args.quiet)

    if args.targets == ["solve"]:
        sol = ctx.engine.best(ctx.problem(args.capacity, args.shift_hours or None))
        stats = sol.balance_stats(ctx.base_time, ctx.overnight_min)
        print(sol.summary())
        print({k: round(v, 2) for k, v in stats.items()})
        for r, km, d in zip(sol.routes, sol.route_km, sol.durations_min(ctx.base_time)):
            print(f"  {km:7.1f} km {d / 60:5.1f} h  {'-'.join(map(str, r))}")
        return 0

    targets = ORDER if "all" in args.targets else [t for t in ORDER if t in args.targets]
    unknown = set(args.targets) - set(ORDER) - {"all"}
    if unknown:
        raise SystemExit(f"unknown target(s): {sorted(unknown)}")
    for target in targets:
        t0 = time.perf_counter()
        COMPONENTS[target](ctx)
        ctx.log(f"   [{target} done in {time.perf_counter() - t0:,.0f} s]")
    return 0
