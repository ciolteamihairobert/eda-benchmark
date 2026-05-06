"""Unit tests for statistical_tests.py using synthetic data."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from statistical_tests import (
    TestResult,
    _compute_test_result,
    _effect_label,
    format_results_table,
)
from utils import describe_series


def test_mann_whitney_detects_difference() -> None:
    """Clearly separated distributions should yield a significant result favouring Go."""
    rng = np.random.default_rng(42)
    dotnet = rng.normal(200, 20, 1000)
    go = rng.normal(150, 20, 1000)
    result = _compute_test_result(dotnet, go, "P95 Latency", "ms", n_bootstrap=200)

    assert result.significant
    assert result.winner == "go"
    assert result.p_value < 0.05


def test_mann_whitney_no_difference() -> None:
    """Identically distributed samples should produce no winner."""
    rng = np.random.default_rng(0)
    dotnet = rng.normal(150, 20, 1000)
    go = rng.normal(150, 20, 1000)
    result = _compute_test_result(dotnet, go, "P95 Latency", "ms", n_bootstrap=200)

    assert not result.significant
    assert result.winner == "tie"


def test_bootstrap_ci_contains_true_diff() -> None:
    """The 95% bootstrap CI should bracket the true mean difference."""
    rng = np.random.default_rng(7)
    true_diff = 50
    dotnet = rng.normal(200, 15, 2000)
    go = rng.normal(150, 15, 2000)
    result = _compute_test_result(dotnet, go, "Latency", "ms", n_bootstrap=2000)

    assert result.ci_low < true_diff < result.ci_high


def test_effect_size_large() -> None:
    """Very different distributions should report a large effect size."""
    rng = np.random.default_rng(1)
    dotnet = rng.normal(300, 10, 500)
    go = rng.normal(100, 10, 500)
    result = _compute_test_result(dotnet, go, "Latency", "ms", n_bootstrap=200)

    assert result.effect_label == "large"


def test_effect_size_negligible() -> None:
    """Near-identical distributions should report a negligible effect size."""
    rng = np.random.default_rng(2)
    dotnet = rng.normal(150, 20, 500)
    go = rng.normal(151, 20, 500)
    result = _compute_test_result(dotnet, go, "Latency", "ms", n_bootstrap=200)

    assert result.effect_label == "negligible"


def test_describe_series() -> None:
    """describe_series should return correctly ordered quantiles and an accurate count."""
    s = pd.Series([1, 2, 3, 4, 5, 100])
    d = describe_series(s)

    assert d["p99"] > d["p95"] > d["p50"]
    assert d["count"] == 6
    assert d["max"] == pytest.approx(100.0)


def test_format_results_table_markdown() -> None:
    """format_results_table should produce a Markdown pipe table with expected content."""
    result = TestResult(
        metric="P95 Latency",
        dotnet_mean=200.0,
        go_mean=150.0,
        mean_diff=50.0,
        ci_low=40.0,
        ci_high=60.0,
        u_stat=12345.0,
        p_value=0.0001,
        significant=True,
        effect_size=0.42,
        effect_label="medium",
        winner="go",
        unit="ms",
    )
    table = format_results_table([result])

    assert "|" in table
    assert "P95 Latency" in table
    assert "GO" in table


def test_effect_label_boundaries() -> None:
    """_effect_label should respect the Cliff's delta magnitude thresholds."""
    assert _effect_label(0.10) == "negligible"
    assert _effect_label(0.20) == "small"
    assert _effect_label(0.40) == "medium"
    assert _effect_label(0.50) == "large"
    assert _effect_label(0.999) == "large"
