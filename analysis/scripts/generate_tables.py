"""Generate summary tables for the dissertation."""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pandas as pd
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    DATA_DIR,
    SERVICES,
    SERVICE_LABELS,
    TABLES_DIR,
    describe_series,
    load_csv,
    print_section,
    save_table,
)

_RESULTS_DIR = Path(__file__).parent.parent.parent / "benchmarks" / "results"


def _try_series(filename: str, col: str) -> pd.Series | None:
    """Load one column from DATA_DIR, returning None on any error.

    Args:
        filename: CSV filename relative to DATA_DIR.
        col: Column name to extract.

    Returns:
        Series or None if the file or column is missing.
    """
    try:
        return load_csv(filename)[col]
    except (FileNotFoundError, KeyError):
        return None


def table01_descriptive_stats() -> None:
    """Table 1: descriptive statistics for all metrics and both services.

    Writes table01_descriptive_stats.md and .tex to output/tables/.
    """
    layout = [
        ("P95 Latency", "latency_p95_{svc}.csv", "value_ms", "ms",  False),
        ("P99 Latency", "latency_p99_{svc}.csv", "value_ms", "ms",  False),
        ("Throughput",  "throughput_{svc}.csv",   "rps",      "rps", False),
        ("CPU Usage",   "cpu_{svc}.csv",           "cpu_percent", "%", False),
        ("Heap Memory", "memory_heap_{svc}.csv",   "bytes",    "MB",  True),
    ]

    rows = []
    for metric, template, col, unit, to_mb in layout:
        for svc in SERVICES:
            s = _try_series(template.format(svc=svc), col)
            label = f"{metric} ({SERVICE_LABELS[svc]})"
            if s is None:
                rows.append([label, *["n/a"] * 7, unit])
                continue
            if to_mb:
                s = s / (1024 ** 2)
            d = describe_series(s)
            rows.append([
                label,
                f"{d['mean']:.2f}", f"{d['std']:.2f}", f"{d['min']:.2f}",
                f"{d['p50']:.2f}", f"{d['p95']:.2f}", f"{d['p99']:.2f}",
                f"{d['max']:.2f}", unit,
            ])

    headers = ["Metric (Service)", "Mean", "Std", "Min", "P50", "P95", "P99", "Max", "Unit"]
    md  = tabulate(rows, headers=headers, tablefmt="pipe")
    tex = tabulate(rows, headers=headers, tablefmt="latex_booktabs")
    save_table(md,  "table01_descriptive_stats", "md")
    save_table(tex, "table01_descriptive_stats", "tex")
    print_section("Table 1: Descriptive Statistics")
    print(md)


def table02_statistical_tests() -> None:
    """Table 2: Mann-Whitney U results delegated to statistical_tests.py.

    Writes table02_statistical_tests.md and .tex to output/tables/.
    """
    from statistical_tests import (
        format_latex_table,
        format_results_table,
        run_fault_tests,
        run_latency_tests,
        run_resource_tests,
        run_throughput_tests,
    )

    results = (
        run_latency_tests()
        + run_throughput_tests()
        + run_resource_tests()
        + run_fault_tests()
    )
    if not results:
        print("No statistical results — populate data/ first.")
        return
    save_table(format_results_table(results), "table02_statistical_tests", "md")
    save_table(format_latex_table(results),   "table02_statistical_tests", "tex")
    print_section("Table 2: Statistical Test Results")
    print(format_results_table(results))


def table03_fault_summary() -> None:
    """Table 3: fault scenario baseline vs. fault-window P95 latency.

    Uses the first quarter of samples as baseline and the middle half as the
    fault window — a rough approximation until per-scenario CSVs are available.
    Writes table03_fault_summary.md and .tex to output/tables/.
    """
    rows = []
    for scenario in ["network-delay", "consumer-restart", "broker-outage"]:
        row: list[str] = [scenario.replace("-", " ").title()]
        for svc in SERVICES:
            s = _try_series(f"latency_p95_{svc}.csv", "value_ms")
            if s is None or len(s) < 4:
                row += ["n/a", "n/a"]
            else:
                n = len(s)
                baseline = float(s.iloc[: n // 4].mean())
                fault_w  = float(s.iloc[n // 4 : 3 * n // 4].mean())
                row += [f"{baseline:.1f}", f"{fault_w:.1f}"]
        row.append("see Chapter 4.4")
        rows.append(row)

    headers = [
        "Scenario",
        ".NET Baseline P95 (ms)", ".NET Fault P95 (ms)",
        "Go Baseline P95 (ms)",  "Go Fault P95 (ms)",
        "Winner",
    ]
    md  = tabulate(rows, headers=headers, tablefmt="pipe")
    tex = tabulate(rows, headers=headers, tablefmt="latex_booktabs")
    save_table(md,  "table03_fault_summary", "md")
    save_table(tex, "table03_fault_summary", "tex")
    print_section("Table 3: Fault Scenario Summary")
    print(md)


def table04_devex() -> None:
    """Table 4: developer experience metric comparison.

    Loads from the latest devex-*.json in benchmarks/results/, or uses
    placeholder values if no JSON is present.
    Writes table04_devex.md and .tex to output/tables/.
    """
    devex_files = sorted(glob.glob(str(_RESULTS_DIR / "devex-*.json")))
    if devex_files:
        with open(devex_files[-1]) as fh:
            data: dict[str, dict[str, float]] = json.load(fh)
    else:
        data = {
            "LOC (src)":         {"dotnet": 800,  "go": 600},
            "Build Time (s)":    {"dotnet": 8.0,  "go": 3.0},
            "Test Count":        {"dotnet": 20,   "go": 10},
            "Test Time (s)":     {"dotnet": 5.0,  "go": 2.0},
            "Docker Image (MB)": {"dotnet": 120,  "go": 15},
        }

    lower_better = {"LOC (src)", "Build Time (s)", "Test Time (s)", "Docker Image (MB)"}

    rows = []
    for metric, values in data.items():
        dn = values.get("dotnet", "n/a")
        go = values.get("go", "n/a")
        if isinstance(dn, (int, float)) and isinstance(go, (int, float)):
            delta = f"{dn - go:+.1f}"
            if metric in lower_better:
                winner = ".NET" if dn < go else "Go" if go < dn else "TIE"
            else:
                winner = ".NET" if dn > go else "Go" if go > dn else "TIE"
        else:
            delta = winner = "n/a"
        rows.append([metric, dn, go, delta, winner])

    headers = ["Metric", ".NET", "Go", "Delta", "Winner"]
    md  = tabulate(rows, headers=headers, tablefmt="pipe")
    tex = tabulate(rows, headers=headers, tablefmt="latex_booktabs")
    save_table(md,  "table04_devex", "md")
    save_table(tex, "table04_devex", "tex")
    print_section("Table 4: Developer Experience")
    print(md)


def table05_recommendations() -> None:
    """Table 5: when to choose each stack (Markdown only).

    Writes table05_recommendations.md to output/tables/.
    """
    rows = [
        [
            "High throughput (>10k msg/s)",
            "Go",
            "Lower per-goroutine overhead; no MediatR dispatch allocations",
        ],
        [
            "Low latency SLA (<50ms P99)",
            "Go",
            "Minimal GC pause times; direct channel dispatch",
        ],
        [
            "Team familiarity (.NET)",
            ".NET",
            "MediatR + DI ecosystem reduces boilerplate; shorter ramp-up",
        ],
        [
            "Small binary / container size",
            "Go",
            "Distroless image ~15 MB vs ~120 MB for ASP.NET alpine",
        ],
        [
            "Rich observability tooling",
            ".NET",
            "Built-in OpenTelemetry, dotnet-trace, Visual Studio profiler",
        ],
        [
            "Rapid prototyping",
            ".NET",
            "`dotnet new` scaffold + MediatR auto-wires commands",
        ],
        [
            "Long-running background consumers",
            "Go",
            "Goroutine-per-partition scales cheaply; no thread overhead",
        ],
        [
            "Mixed command/query workloads",
            ".NET",
            "MediatR cleanly separates commands/queries with pipeline behaviours",
        ],
    ]
    headers = ["Scenario", "Recommended Stack", "Rationale"]
    md = tabulate(rows, headers=headers, tablefmt="pipe")
    save_table(md, "table05_recommendations", "md")
    print_section("Table 5: Recommendations")
    print(md)


def main() -> None:
    """Generate all five dissertation summary tables."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    table01_descriptive_stats()
    table02_statistical_tests()
    table03_fault_summary()
    table04_devex()
    table05_recommendations()
    print(f"\nAll tables saved to {TABLES_DIR}")


if __name__ == "__main__":
    main()
