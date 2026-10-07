"""Analysis components C0-C5 of the paper, plus the summary report."""

from . import c0_replication, c1_gap, c2_capacity, c3_duration, c4_incidence, c5_robustness, report

COMPONENTS = {
    "c0": c0_replication.run,
    "c1": c1_gap.run,
    "c2": c2_capacity.run,
    "c3": c3_duration.run,
    "c4": c4_incidence.run,
    "c5": c5_robustness.run,
    "report": report.run,
}

__all__ = ["COMPONENTS"]
