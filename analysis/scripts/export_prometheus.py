"""Export Prometheus metrics to CSV files for offline analysis."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from utils import DATA_DIR, PROMETHEUS_URL


def query_range(
    query: str,
    start: datetime,
    end: datetime,
    step: int,
    prom_url: str,
) -> pd.DataFrame:
    """Query the Prometheus range API and return a tidy DataFrame.

    Args:
        query: PromQL expression.
        start: Query start time (UTC-aware).
        end: Query end time (UTC-aware).
        step: Resolution in seconds.
        prom_url: Prometheus base URL (no trailing slash).

    Returns:
        DataFrame with columns [timestamp, value] where timestamp is UTC datetime.
        Returns an empty DataFrame if the query yields no data.

    Raises:
        requests.HTTPError: If the Prometheus API returns a non-2xx status.
    """
    url = f"{prom_url}/api/v1/query_range"
    params: dict[str, Any] = {
        "query": query,
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": step,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("data", {}).get("result", [])
    if not results:
        return pd.DataFrame(columns=["timestamp", "value"])

    rows = []
    for series in results:
        for ts, val in series["values"]:
            rows.append(
                {
                    "timestamp": datetime.fromtimestamp(float(ts), tz=timezone.utc),
                    "value": float(val),
                }
            )
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def query_range_labeled(
    query: str,
    label_col: str,
    start: datetime,
    end: datetime,
    step: int,
    prom_url: str,
) -> pd.DataFrame:
    """Query Prometheus and return a multi-series DataFrame with a label column.

    Args:
        query: PromQL expression that returns multiple series.
        label_col: Metric label name to extract as a DataFrame column (e.g. 'topic').
        start: Query start time (UTC-aware).
        end: Query end time (UTC-aware).
        step: Resolution in seconds.
        prom_url: Prometheus base URL.

    Returns:
        DataFrame with columns [timestamp, <label_col>, value].
    """
    url = f"{prom_url}/api/v1/query_range"
    params: dict[str, Any] = {
        "query": query,
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": step,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("data", {}).get("result", [])
    if not results:
        return pd.DataFrame(columns=["timestamp", label_col, "value"])

    rows = []
    for series in results:
        label_val = series["metric"].get(label_col, "unknown")
        for ts, val in series["values"]:
            rows.append(
                {
                    "timestamp": datetime.fromtimestamp(float(ts), tz=timezone.utc),
                    label_col: label_val,
                    "value": float(val),
                }
            )
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def _write_csv(df: pd.DataFrame, path: Path, rename_value: str = "value") -> None:
    """Write a DataFrame to CSV, optionally renaming the 'value' column.

    Args:
        df: DataFrame to write.
        path: Destination CSV path.
        rename_value: New name for the 'value' column.
    """
    if rename_value != "value" and "value" in df.columns:
        df = df.rename(columns={"value": rename_value})
    df.to_csv(path, index=False)
    print(f"Exported {path.name} ({len(df)} rows)")


def export_all(
    start: datetime,
    end: datetime,
    step: int,
    prom_url: str,
    out_dir: Path,
) -> None:
    """Export all benchmark metrics from Prometheus to CSV files.

    Args:
        start: Query start time (UTC-aware).
        end: Query end time (UTC-aware).
        step: Scrape resolution in seconds.
        prom_url: Prometheus base URL.
        out_dir: Directory to write CSV files (created if missing).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    def qr(query: str) -> pd.DataFrame:
        return query_range(query, start, end, step, prom_url)

    def qrl(query: str, label: str) -> pd.DataFrame:
        return query_range_labeled(query, label, start, end, step, prom_url)

    k6_bucket = "k6_http_req_duration_milliseconds_bucket"

    # ── Latency percentiles ──────────────────────────────────────────────────
    for pct_label, pct_val in [
        ("p50", 0.50), ("p75", 0.75), ("p90", 0.90), ("p95", 0.95), ("p99", 0.99)
    ]:
        for svc in ("dotnet", "go"):
            q = (
                f"histogram_quantile({pct_val}, "
                f'sum(rate({k6_bucket}{{service="{svc}"}}[1m])) by (le))'
            )
            _write_csv(qr(q), out_dir / f"latency_{pct_label}_{svc}.csv", "value_ms")

    # ── Throughput ────────────────────────────────────────────────────────────
    for svc in ("dotnet", "go"):
        q = f'sum(rate(k6_http_reqs_total{{service="{svc}"}}[1m]))'
        _write_csv(qr(q), out_dir / f"throughput_{svc}.csv", "rps")

    # ── Error rate ────────────────────────────────────────────────────────────
    for svc in ("dotnet", "go"):
        q = (
            f'sum(rate(k6_http_req_failed_total{{service="{svc}"}}[1m])) / '
            f'sum(rate(k6_http_reqs_total{{service="{svc}"}}[1m]))'
        )
        _write_csv(qr(q), out_dir / f"error_rate_{svc}.csv", "rate")

    # ── CPU utilisation ───────────────────────────────────────────────────────
    for svc, job in [("dotnet", "dotnet-service"), ("go", "go-service")]:
        q = f'rate(process_cpu_seconds_total{{job="{job}"}}[1m]) * 100'
        _write_csv(qr(q), out_dir / f"cpu_{svc}.csv", "cpu_percent")

    # ── Heap memory ───────────────────────────────────────────────────────────
    _write_csv(
        qr('dotnet_gc_heap_size_bytes{job="dotnet-service"}'),
        out_dir / "memory_heap_dotnet.csv",
        "bytes",
    )
    _write_csv(
        qr('go_memstats_heap_inuse_bytes{job="go-service"}'),
        out_dir / "memory_heap_go.csv",
        "bytes",
    )

    # ── Kafka consumer lag ────────────────────────────────────────────────────
    for svc, cg in [("dotnet", "dotnet-order-service"), ("go", "go-order-service")]:
        q = f'sum(kafka_consumergroup_lag{{consumergroup="{cg}"}}) by (topic)'
        _write_csv(qrl(q, "topic"), out_dir / f"consumer_lag_{svc}.csv", "lag")

    # ── Orders counters ───────────────────────────────────────────────────────
    for event in ("received", "processed", "failed"):
        for svc, job in [("dotnet", "dotnet-service"), ("go", "go-service")]:
            q = f'orders_{event}_total{{job="{job}"}}'
            _write_csv(qr(q), out_dir / f"orders_{event}_{svc}.csv", "total")


def _parse_args() -> argparse.Namespace:
    now = datetime.now(tz=timezone.utc)
    p = argparse.ArgumentParser(description="Export Prometheus metrics to CSV.")
    p.add_argument(
        "--start",
        default=(now - timedelta(hours=2)).isoformat(),
        help="ISO8601 start time (default: now-2h)",
    )
    p.add_argument(
        "--end",
        default=now.isoformat(),
        help="ISO8601 end time (default: now)",
    )
    p.add_argument("--step", type=int, default=10, help="Resolution in seconds (default: 10)")
    p.add_argument("--prometheus", default=PROMETHEUS_URL, help="Prometheus base URL")
    p.add_argument("--out", type=Path, default=DATA_DIR, help="Output directory")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    def _parse_ts(s: str) -> datetime:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    start_dt = _parse_ts(args.start)
    end_dt = _parse_ts(args.end)

    print(f"Exporting metrics: {start_dt.isoformat()} → {end_dt.isoformat()}")
    print(f"Prometheus: {args.prometheus}")
    print(f"Output:     {args.out}\n")

    export_all(start_dt, end_dt, args.step, args.prometheus, args.out)
    print("\nExport complete.")
