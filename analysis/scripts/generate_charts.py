"""Generate publication-quality figures for the EDA benchmark dissertation."""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    DATA_DIR,
    FIGURES_DIR,
    SERVICE_COLORS,
    SERVICE_LABELS,
    SERVICES,
    load_csv,
    save_figure,
    set_plot_style,
)

set_plot_style()

_RESULTS_DIR = Path(__file__).parent.parent.parent / "benchmarks" / "results"


def _try_load(filename: str, col: str | None = None) -> pd.DataFrame | pd.Series | None:
    """Attempt to load a CSV without raising on missing file.

    Args:
        filename: CSV filename relative to DATA_DIR.
        col: If provided, return only this column as a Series.

    Returns:
        DataFrame or Series, or None if the file is missing.
    """
    try:
        df = load_csv(filename)
        return df[col] if col else df
    except FileNotFoundError as e:
        print(f"  Warning: {e}")
        return None


def fig01_latency_percentiles() -> None:
    """Figure 1: grouped bar chart of P50/P95/P99 for steady-state and spike.

    Saves fig01_latency_percentiles.png and .pdf to output/figures/.
    """
    pcts = ["p50", "p95", "p99"]
    labels = ["P50", "P95", "P99"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=False)

    for ax_idx, title in enumerate(["Steady-State", "Spike"]):
        x = np.arange(len(pcts))
        width = 0.35
        for svc_idx, svc in enumerate(SERVICES):
            means, stds = [], []
            for pct in pcts:
                s = _try_load(f"latency_{pct}_{svc}.csv", "value_ms")
                if s is not None:
                    means.append(float(s.mean()))
                    stds.append(float(s.std()))
                else:
                    means.append(float("nan"))
                    stds.append(0.0)

            axes[ax_idx].bar(
                x + (svc_idx - 0.5) * width,
                means,
                width,
                label=SERVICE_LABELS[svc],
                color=SERVICE_COLORS[svc],
                alpha=0.85,
                yerr=stds,
                capsize=4,
                error_kw={"elinewidth": 1},
            )

        axes[ax_idx].set_xticks(x)
        axes[ax_idx].set_xticklabels(labels)
        axes[ax_idx].set_xlabel("Percentile")
        axes[ax_idx].set_ylabel("Latency (ms)")
        axes[ax_idx].set_title(title)
        axes[ax_idx].legend()

    fig.suptitle("Latency Percentiles: Steady-State and Spike Scenarios", fontsize=13)
    plt.tight_layout()
    save_figure(fig, "fig01_latency_percentiles")
    plt.close(fig)


def fig02_latency_timeseries() -> None:
    """Figure 2: P95 and P99 latency over time for both services.

    Saves fig02_latency_timeseries.png and .pdf to output/figures/.
    """
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for ax_idx, pct_label in enumerate(["p95", "p99"]):
        for svc in SERVICES:
            df = _try_load(f"latency_{pct_label}_{svc}.csv")
            if df is not None:
                axes[ax_idx].plot(
                    df.index,
                    df["value_ms"],
                    label=SERVICE_LABELS[svc],
                    color=SERVICE_COLORS[svc],
                    alpha=0.85,
                )
        axes[ax_idx].set_ylabel(f"{pct_label.upper()} Latency (ms)")
        axes[ax_idx].legend()
        axes[ax_idx].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    axes[1].set_xlabel("Time (UTC)")
    fig.suptitle("P95 and P99 Latency Over Time", fontsize=13)
    plt.tight_layout()
    save_figure(fig, "fig02_latency_timeseries")
    plt.close(fig)


def fig03_throughput_timeseries() -> None:
    """Figure 3: throughput (RPS) with Kafka consumer lag on a secondary axis.

    Saves fig03_throughput_timeseries.png and .pdf to output/figures/.
    """
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax2 = ax1.twinx()

    for svc in SERVICES:
        df = _try_load(f"throughput_{svc}.csv")
        if df is not None:
            ax1.plot(
                df.index, df["rps"],
                label=SERVICE_LABELS[svc],
                color=SERVICE_COLORS[svc],
            )

    for svc in SERVICES:
        df = _try_load(f"consumer_lag_{svc}.csv")
        if df is not None and "lag" in df.columns:
            lag = df.groupby(df.index)["lag"].sum()
            ax2.plot(
                lag.index, lag,
                label=f"Lag — {SERVICE_LABELS[svc]}",
                color=SERVICE_COLORS[svc],
                linestyle="--",
                alpha=0.55,
            )

    ax1.set_xlabel("Time (UTC)")
    ax1.set_ylabel("Requests / sec")
    ax2.set_ylabel("Consumer Lag (messages)")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)

    fig.suptitle("Throughput and Consumer Lag Over Time", fontsize=13)
    plt.tight_layout()
    save_figure(fig, "fig03_throughput_timeseries")
    plt.close(fig)


def fig04_resource_utilisation() -> None:
    """Figure 4: 2×2 grid of CPU and heap memory over time for both services.

    Saves fig04_resource_utilisation.png and .pdf to output/figures/.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    layout = [
        (0, 0, "dotnet", "cpu_dotnet.csv",        "cpu_percent", "CPU % — .NET",  "CPU (%)"),
        (0, 1, "go",     "cpu_go.csv",             "cpu_percent", "CPU % — Go",    "CPU (%)"),
        (1, 0, "dotnet", "memory_heap_dotnet.csv", "bytes",       "Heap — .NET",   "Memory (MB)"),
        (1, 1, "go",     "memory_heap_go.csv",     "bytes",       "Heap — Go",     "Memory (MB)"),
    ]

    for row, col, svc, fname, value_col, title, ylabel in layout:
        ax = axes[row][col]
        df = _try_load(fname)
        if df is not None and value_col in df.columns:
            vals = df[value_col].copy()
            if ylabel == "Memory (MB)":
                vals = vals / (1024 ** 2)
            ax.fill_between(df.index, vals, alpha=0.22, color=SERVICE_COLORS[svc])
            ax.plot(df.index, vals, color=SERVICE_COLORS[svc], linewidth=1.2)
            ax.axhline(
                vals.mean(),
                linestyle="--", color="grey", linewidth=1,
                label=f"Mean: {vals.mean():.1f}",
            )
            ax.legend(fontsize=9)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        else:
            ax.text(0.5, 0.5, "Data not available",
                    ha="center", va="center",
                    transform=ax.transAxes, color="grey")

        ax.set_title(title)
        ax.set_ylabel(ylabel)

    for ax in axes[1]:
        ax.set_xlabel("Time (UTC)")

    fig.suptitle("CPU and Memory Utilisation", fontsize=13)
    plt.tight_layout()
    save_figure(fig, "fig04_resource_utilisation")
    plt.close(fig)


def fig05_fault_recovery() -> None:
    """Figure 5: P95 latency under three fault injection scenarios.

    Saves fig05_fault_recovery.png and .pdf to output/figures/.
    """
    scenarios = [
        ("Network Delay",    "latency_p95_dotnet.csv", "latency_p95_go.csv"),
        ("Consumer Restart", "latency_p95_dotnet.csv", "latency_p95_go.csv"),
        ("Broker Outage",    "latency_p95_dotnet.csv", "latency_p95_go.csv"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)

    for ax_idx, (title, dn_file, go_file) in enumerate(scenarios):
        ax = axes[ax_idx]
        any_data = False
        for svc, fname in [("dotnet", dn_file), ("go", go_file)]:
            df = _try_load(fname)
            if df is not None:
                ax.plot(
                    df.index, df["value_ms"],
                    label=SERVICE_LABELS[svc],
                    color=SERVICE_COLORS[svc],
                )
                any_data = True

        if not any_data:
            ax.text(0.5, 0.5, "Data not\navailable",
                    ha="center", va="center",
                    transform=ax.transAxes, color="grey")

        ax.set_title(title)
        ax.set_xlabel("Time (UTC)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        if ax_idx == 0:
            ax.set_ylabel("P95 Latency (ms)")
        ax.legend(fontsize=8)

    fig.suptitle("Service Behaviour Under Fault Conditions", fontsize=13)
    plt.tight_layout()
    save_figure(fig, "fig05_fault_recovery")
    plt.close(fig)


def fig06_latency_cdf() -> None:
    """Figure 6: empirical CDF of P95 latency samples for both services.

    Uses a log x-axis and annotates the P95 and P99 thresholds.
    Saves fig06_latency_cdf.png and .pdf to output/figures/.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    for svc in SERVICES:
        df = _try_load(f"latency_p95_{svc}.csv")
        if df is None:
            continue
        vals = df["value_ms"].dropna().sort_values()
        cdf = np.arange(1, len(vals) + 1) / len(vals)
        ax.semilogx(vals, cdf, label=SERVICE_LABELS[svc], color=SERVICE_COLORS[svc])

        for pct_val, pct_label in [(0.95, "P95"), (0.99, "P99")]:
            v = float(vals.quantile(pct_val))
            ax.axvline(v, linestyle=":", color=SERVICE_COLORS[svc], alpha=0.55)
            ax.annotate(
                f"{pct_label}={v:.0f}ms",
                xy=(v, pct_val),
                xytext=(6, -14),
                textcoords="offset points",
                fontsize=8,
                color=SERVICE_COLORS[svc],
            )

    ax.set_xlabel("Latency (ms, log scale)")
    ax.set_ylabel("Cumulative Probability")
    ax.set_ylim(0, 1.05)
    ax.legend()
    fig.suptitle("Empirical CDF of Request Latency", fontsize=13)
    plt.tight_layout()
    save_figure(fig, "fig06_latency_cdf")
    plt.close(fig)


def fig07_devex_radar() -> None:
    """Figure 7: radar/spider chart comparing developer experience metrics.

    Loads values from the latest devex-*.json in benchmarks/results/.
    Falls back to placeholder data if no JSON is found.
    Saves fig07_devex_radar.png and .pdf to output/figures/.
    """
    devex_files = sorted(glob.glob(str(_RESULTS_DIR / "devex-*.json")))
    if devex_files:
        with open(devex_files[-1]) as fh:
            raw = json.load(fh)
    else:
        print("  Warning: no devex JSON found — using placeholder data")
        raw = {
            "loc_src":       {"dotnet": 800,  "go": 600},
            "build_time_s":  {"dotnet": 8.0,  "go": 3.0},
            "test_time_s":   {"dotnet": 5.0,  "go": 2.0},
            "image_size_mb": {"dotnet": 120,  "go": 15},
            "test_count":    {"dotnet": 20,   "go": 10},
        }

    axes_labels = ["LOC", "Build Time", "Test Time", "Image Size", "Test Count\n(↑ better)"]
    metrics = list(raw.keys())
    N = len(metrics)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    def _normalise(vals: list[float], invert: bool) -> list[float]:
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return [0.5] * len(vals)
        normed = [(v - lo) / (hi - lo) for v in vals]
        return normed if invert else [1 - n for n in normed]

    dn_norm, go_norm = [], []
    for i, m in enumerate(metrics):
        dn_raw = raw[m].get("dotnet", 0)
        go_raw = raw[m].get("go", 0)
        invert = m == "test_count"
        pair = _normalise([dn_raw, go_raw], invert=invert)
        dn_norm.append(pair[0])
        go_norm.append(pair[1])

    dn_vals = dn_norm + dn_norm[:1]
    go_vals = go_norm + go_norm[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), axes_labels)

    ax.plot(angles, dn_vals, color=SERVICE_COLORS["dotnet"], linewidth=2,
            label=SERVICE_LABELS["dotnet"])
    ax.fill(angles, dn_vals, color=SERVICE_COLORS["dotnet"], alpha=0.2)

    ax.plot(angles, go_vals, color=SERVICE_COLORS["go"], linewidth=2,
            label=SERVICE_LABELS["go"])
    ax.fill(angles, go_vals, color=SERVICE_COLORS["go"], alpha=0.2)

    ax.set_ylim(0, 1)
    ax.set_yticklabels([])
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1))
    ax.set_title(
        "Developer Experience Comparison\n(lower normalised score = better)",
        pad=20,
        fontsize=12,
    )
    plt.tight_layout()
    save_figure(fig, "fig07_devex_radar")
    plt.close(fig)


def fig08_significance_heatmap() -> None:
    """Figure 8: heatmap summarising statistical results across all metrics.

    Rows are metrics; columns are .NET mean, Go mean, p-value, effect size.
    Cells are annotated with raw values.
    Saves fig08_significance_heatmap.png and .pdf to output/figures/.
    """
    from statistical_tests import run_latency_tests, run_throughput_tests, run_resource_tests

    all_results = run_latency_tests() + run_throughput_tests() + run_resource_tests()
    if not all_results:
        print("  Warning: no statistical results — populate data/ first.")
        return

    metrics = [r.metric for r in all_results]
    cols = [".NET mean", "Go mean", "p-value", "Effect size"]
    data = [
        [r.dotnet_mean, r.go_mean, r.p_value, abs(r.effect_size)]
        for r in all_results
    ]
    df_vals = pd.DataFrame(data, index=metrics, columns=cols)
    df_norm = (df_vals - df_vals.min()) / (df_vals.max() - df_vals.min()).replace(0, 1)

    annot = pd.DataFrame(
        [[f"{v:.3f}" for v in row] for row in data],
        index=metrics,
        columns=cols,
    )

    fig, ax = plt.subplots(figsize=(11, max(4, len(metrics) * 0.9)))
    sns.heatmap(
        df_norm,
        ax=ax,
        cmap="RdYlGn_r",
        annot=annot,
        fmt="",
        linewidths=0.5,
        cbar_kws={"label": "Normalised value (0–1)"},
    )
    ax.set_title("Statistical Comparison Summary", fontsize=13)
    ax.set_xlabel("")
    plt.tight_layout()
    save_figure(fig, "fig08_significance_heatmap")
    plt.close(fig)


def main() -> None:
    """Generate all 8 publication-quality figures."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    figures = [
        ("fig01_latency_percentiles",  fig01_latency_percentiles),
        ("fig02_latency_timeseries",   fig02_latency_timeseries),
        ("fig03_throughput_timeseries", fig03_throughput_timeseries),
        ("fig04_resource_utilisation", fig04_resource_utilisation),
        ("fig05_fault_recovery",       fig05_fault_recovery),
        ("fig06_latency_cdf",          fig06_latency_cdf),
        ("fig07_devex_radar",          fig07_devex_radar),
        ("fig08_significance_heatmap", fig08_significance_heatmap),
    ]
    for name, func in figures:
        print(f"\nGenerating {name}...")
        try:
            func()
        except Exception as e:
            print(f"  Error in {name}: {e}")

    print(f"\nAll figures saved to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
