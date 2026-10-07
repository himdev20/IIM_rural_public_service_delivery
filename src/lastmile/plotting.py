"""Consistent, print-friendly figure styling."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PALETTE = ["#1b4f72", "#c0392b", "#d68910", "#1e8449", "#6c3483", "#5d6d7e", "#117a65"]
GREY = "#7f8c8d"


def setup() -> None:
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
        "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.25, "legend.frameon": False,
        "axes.prop_cycle": matplotlib.cycler(color=PALETTE),
    })


def save(fig, path: Path) -> Path:
    fig.savefig(path)
    plt.close(fig)
    return path


setup()
