"""Shared utilities for the EDA benchmark analysis pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

DATA_DIR: Path = Path(__file__).parent.parent / "data"
OUTPUT_DIR: Path = Path(__file__).parent.parent / "output"
FIGURES_DIR: Path = OUTPUT_DIR / "figures"
TABLES_DIR: Path = OUTPUT_DIR / "tables"
REPORT_DIR: Path = OUTPUT_DIR / "report"

SERVICES: list[str] = ["dotnet", "go"]
SERVICE_COLORS: dict[str, str] = {
    "dotnet": "#512BD4",
    "go": "#00ACD7",
}
SERVICE_LABELS: dict[str, str] = {
    "dotnet": ".NET (MediatR + Kafka)",
    "go": "Go (goroutines + kafka-go)",
}
PERCENTILES: list[float] = [0.50, 0.75, 0.90, 0.95, 0.99]


def load_csv(filename: str) -> pd.DataFrame:
    """Load a CSV from DATA_DIR and parse the timestamp column as the index.

    Args:
        filename: Filename relative to DATA_DIR (e.g. 'latency_p95_dotnet.csv').

    Returns:
        DataFrame with a datetime index named 'timestamp'.

    Raises:
        FileNotFoundError: If the file does not exist, with a hint to run
            export_prometheus.py first.
    """
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}\n"
            f"Run scripts/export_prometheus.py first to generate data/{filename}"
        )
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.set_index("timestamp")
    return df


def save_figure(fig: plt.Figure, name: str, dpi: int = 300) -> None:
    """Save a matplotlib figure as both PNG and PDF.

    Args:
        fig: The matplotlib Figure to save.
        name: Base filename without extension (e.g. 'fig01_latency_percentiles').
        dpi: Resolution for raster output. Defaults to 300.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        path = FIGURES_DIR / f"{name}.{ext}"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        print(f"Saved: {path}")


def save_table(content: str, name: str, fmt: str = "md") -> None:
    """Save table content to TABLES_DIR.

    Args:
        content: The table string to write.
        name: Base filename without extension.
        fmt: File extension, either 'md' or 'tex'. Defaults to 'md'.
    """
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLES_DIR / f"{name}.{fmt}"
    path.write_text(content, encoding="utf-8")
    print(f"Saved: {path}")


def set_plot_style() -> None:
    """Configure matplotlib rcParams for publication-quality figures."""
    plt.rcParams.update(
        {
            "figure.figsize": (10, 5),
            "figure.dpi": 150,
            "font.family": "serif",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "lines.linewidth": 1.5,
        }
    )


def describe_series(s: pd.Series, label: str = "") -> dict[str, Any]:
    """Compute descriptive statistics for a numeric series.

    Args:
        s: Input numeric Series.
        label: Optional prefix applied to all returned keys.

    Returns:
        Dict with keys: mean, std, min, p50, p75, p90, p95, p99, max, count.
        All keys are prefixed with '{label}_' if label is provided.
    """
    prefix = f"{label}_" if label else ""
    q = s.quantile([0.50, 0.75, 0.90, 0.95, 0.99])
    return {
        f"{prefix}mean":  float(s.mean()),
        f"{prefix}std":   float(s.std()),
        f"{prefix}min":   float(s.min()),
        f"{prefix}p50":   float(q[0.50]),
        f"{prefix}p75":   float(q[0.75]),
        f"{prefix}p90":   float(q[0.90]),
        f"{prefix}p95":   float(q[0.95]),
        f"{prefix}p99":   float(q[0.99]),
        f"{prefix}max":   float(s.max()),
        f"{prefix}count": int(s.count()),
    }


def print_section(title: str) -> None:
    """Print a formatted section header to stdout.

    Args:
        title: Section title text.
    """
    bar = "═" * (len(title) + 4)
    print(f"\n{bar}\n  {title}\n{bar}")
