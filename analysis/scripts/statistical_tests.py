"""Statistical comparison between the .NET and Go EDA services."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).parent))
from utils import DATA_DIR, TABLES_DIR, describe_series, print_section, save_table

try:
    from pingouin import compute_effsize as _ping_effsize
    _HAS_PINGOUIN = True
except ImportError:
    _HAS_PINGOUIN = False


@dataclass
class TestResult:
    """All statistical outputs for one metric comparison."""

    metric: str
    dotnet_mean: float
    go_mean: float
    mean_diff: float
    ci_low: float
    ci_high: float
    u_stat: float
    p_value: float
    significant: bool
    effect_size: float
    effect_label: str
    winner: str
    unit: str


def _effect_label(delta: float) -> str:
    """Map an absolute Cliff's delta to a verbal magnitude label.

    Args:
        delta: Absolute value of Cliff's delta (0–1).

    Returns:
        One of 'negligible', 'small', 'medium', or 'large'.
    """
    abs_d = abs(delta)
    if abs_d < 0.147:
        return "negligible"
    if abs_d < 0.330:
        return "small"
    if abs_d < 0.474:
        return "medium"
    return "large"


def _compute_test_result(
    dotnet_vals: np.ndarray,
    go_vals: np.ndarray,
    metric: str,
    unit: str,
    n_bootstrap: int = 10_000,
    lower_is_better: bool = True,
) -> TestResult:
    """Run Mann-Whitney U, bootstrap CI, and effect size for two samples.

    Args:
        dotnet_vals: 1-D array of .NET measurements.
        go_vals: 1-D array of Go measurements.
        metric: Human-readable metric name for output tables.
        unit: Unit string (e.g. 'ms', 'rps', '%', 'MB').
        n_bootstrap: Number of bootstrap resamples for the CI. Defaults to 10000.
        lower_is_better: If True, the service with a lower mean wins.

    Returns:
        Populated TestResult dataclass.
    """
    dotnet_vals = dotnet_vals[~np.isnan(dotnet_vals)]
    go_vals = go_vals[~np.isnan(go_vals)]

    dotnet_mean = float(np.mean(dotnet_vals))
    go_mean = float(np.mean(go_vals))
    mean_diff = dotnet_mean - go_mean

    u_stat, p_value = mannwhitneyu(dotnet_vals, go_vals, alternative="two-sided")
    significant = bool(p_value < 0.05)

    rng = np.random.default_rng(42)
    diffs = np.array(
        [
            rng.choice(dotnet_vals, size=len(dotnet_vals), replace=True).mean()
            - rng.choice(go_vals, size=len(go_vals), replace=True).mean()
            for _ in range(n_bootstrap)
        ]
    )
    ci_low, ci_high = float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))

    if _HAS_PINGOUIN:
        effect_size = float(
            _ping_effsize(dotnet_vals.tolist(), go_vals.tolist(), eftype="cles")
        )
    else:
        n1, n2 = len(dotnet_vals), len(go_vals)
        effect_size = float((u_stat / (n1 * n2)) * 2 - 1)

    label = _effect_label(effect_size)

    if not significant:
        winner = "tie"
    elif lower_is_better:
        winner = "go" if go_mean < dotnet_mean else "dotnet"
    else:
        winner = "go" if go_mean > dotnet_mean else "dotnet"

    return TestResult(
        metric=metric,
        dotnet_mean=dotnet_mean,
        go_mean=go_mean,
        mean_diff=mean_diff,
        ci_low=ci_low,
        ci_high=ci_high,
        u_stat=float(u_stat),
        p_value=float(p_value),
        significant=significant,
        effect_size=effect_size,
        effect_label=label,
        winner=winner,
        unit=unit,
    )


def _load_values(filename: str, col: str) -> np.ndarray:
    """Load a single numeric column from a CSV in DATA_DIR.

    Args:
        filename: CSV filename relative to DATA_DIR.
        col: Column name to extract.

    Returns:
        NumPy float array with NaN rows removed.

    Raises:
        FileNotFoundError: With a hint to run export_prometheus.py.
    """
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Missing data file: {path}\n"
            "Run scripts/export_prometheus.py first."
        )
    return pd.read_csv(path)[col].dropna().to_numpy(dtype=float)


def run_latency_tests(n_bootstrap: int = 10_000) -> list[TestResult]:
    """Compare P95 and P99 latency between the two services.

    Args:
        n_bootstrap: Bootstrap resamples for CI. Defaults to 10000.

    Returns:
        List of TestResult, one per percentile.
    """
    results: list[TestResult] = []
    for pct_label, metric_name in [("p95", "P95 Latency"), ("p99", "P99 Latency")]:
        try:
            dn = _load_values(f"latency_{pct_label}_dotnet.csv", "value_ms")
            go = _load_values(f"latency_{pct_label}_go.csv", "value_ms")
            results.append(
                _compute_test_result(dn, go, metric_name, "ms", n_bootstrap)
            )
        except FileNotFoundError as e:
            print(f"Warning: skipping {metric_name}: {e}")
    return results


def run_throughput_tests(n_bootstrap: int = 10_000) -> list[TestResult]:
    """Compare request throughput (RPS) between the two services.

    Args:
        n_bootstrap: Bootstrap resamples for CI. Defaults to 10000.

    Returns:
        List containing one TestResult for RPS.
    """
    try:
        dn = _load_values("throughput_dotnet.csv", "rps")
        go = _load_values("throughput_go.csv", "rps")
        return [
            _compute_test_result(
                dn, go, "Throughput", "rps", n_bootstrap, lower_is_better=False
            )
        ]
    except FileNotFoundError as e:
        print(f"Warning: skipping throughput test: {e}")
        return []


def run_resource_tests(n_bootstrap: int = 10_000) -> list[TestResult]:
    """Compare CPU and memory usage between the two services.

    Args:
        n_bootstrap: Bootstrap resamples for CI. Defaults to 10000.

    Returns:
        List of TestResult for CPU (%) and heap memory (MB).
    """
    results: list[TestResult] = []
    pairs = [
        ("cpu_dotnet.csv", "cpu_go.csv", "cpu_percent", "CPU Usage", "%", False),
        ("memory_heap_dotnet.csv", "memory_heap_go.csv", "bytes", "Heap Memory", "MB", False),
    ]
    for dn_file, go_file, col, name, unit, convert_mb in [
        ("cpu_dotnet.csv", "cpu_go.csv", "cpu_percent", "CPU Usage", "%", False),
        ("memory_heap_dotnet.csv", "memory_heap_go.csv", "bytes", "Heap Memory", "MB", True),
    ]:
        try:
            dn = _load_values(dn_file, col)
            go = _load_values(go_file, col)
            if convert_mb:
                dn = dn / (1024 ** 2)
                go = go / (1024 ** 2)
            results.append(_compute_test_result(dn, go, name, unit, n_bootstrap))
        except FileNotFoundError as e:
            print(f"Warning: skipping {name}: {e}")
    return results


def run_fault_tests(n_bootstrap: int = 10_000) -> list[TestResult]:
    """Compare error rates during fault scenarios between the two services.

    Args:
        n_bootstrap: Bootstrap resamples for CI. Defaults to 10000.

    Returns:
        List of TestResult for error rate under fault conditions.
    """
    results: list[TestResult] = []
    try:
        dn = _load_values("error_rate_dotnet.csv", "rate")
        go = _load_values("error_rate_go.csv", "rate")
        results.append(
            _compute_test_result(dn, go, "Error Rate (Fault)", "rate", n_bootstrap)
        )
    except FileNotFoundError as e:
        print(f"Warning: skipping fault error-rate test: {e}")
    return results


def format_results_table(results: list[TestResult]) -> str:
    """Format test results as a Markdown pipe table.

    Args:
        results: List of TestResult instances.

    Returns:
        Markdown table string.
    """
    rows = []
    for r in results:
        ci = f"[{r.ci_low:+.2f}, {r.ci_high:+.2f}]"
        p_str = f"{r.p_value:.4f}" if r.p_value >= 0.0001 else "<0.0001"
        rows.append(
            [
                r.metric,
                f"{r.dotnet_mean:.2f} {r.unit}",
                f"{r.go_mean:.2f} {r.unit}",
                f"{r.mean_diff:+.2f} {r.unit}",
                ci,
                p_str,
                r.effect_label,
                r.winner.upper() if r.winner != "tie" else "TIE",
            ]
        )
    headers = ["Metric", ".NET mean", "Go mean", "Diff", "95% CI", "p-value", "Effect", "Winner"]
    return tabulate(rows, headers=headers, tablefmt="pipe")


def format_latex_table(results: list[TestResult]) -> str:
    """Format test results as a LaTeX booktabs table.

    Args:
        results: List of TestResult instances.

    Returns:
        LaTeX booktabs table string ready for dissertation inclusion.
    """
    rows = []
    for r in results:
        ci = f"[{r.ci_low:+.2f}, {r.ci_high:+.2f}]"
        p_str = f"{r.p_value:.4f}" if r.p_value >= 0.0001 else r"$<$0.0001"
        rows.append(
            [
                r.metric,
                f"{r.dotnet_mean:.2f}",
                f"{r.go_mean:.2f}",
                f"{r.mean_diff:+.2f}",
                ci,
                p_str,
                r.effect_label,
                r.winner.upper() if r.winner != "tie" else "TIE",
            ]
        )
    headers = [
        "Metric",
        r".NET $\bar{x}$",
        r"Go $\bar{x}$",
        "Diff",
        r"95\% CI",
        r"$p$-value",
        "Effect",
        "Winner",
    ]
    return tabulate(rows, headers=headers, tablefmt="latex_booktabs")


def main() -> None:
    """Run all statistical tests and write results to output/tables/."""
    results = (
        run_latency_tests()
        + run_throughput_tests()
        + run_resource_tests()
        + run_fault_tests()
    )

    if not results:
        print("No results — run export_prometheus.py to populate data/ first.")
        return

    print_section("Statistical Test Results")
    print(format_results_table(results))
    save_table(format_results_table(results), "table02_statistical_tests", "md")
    save_table(format_latex_table(results), "table02_statistical_tests", "tex")
    print(f"\nSaved to {TABLES_DIR}")


if __name__ == "__main__":
    main()
