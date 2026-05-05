# Analysis

Statistical analysis pipeline for the `.NET MediatR + Kafka` vs `Go goroutines + kafka-go`
EDA benchmark dissertation.

## What this produces

| Output | Count | Format |
|---|---|---|
| Publication-quality figures | 8 | PNG (300 dpi) + PDF |
| Markdown tables | 5 | `.md` |
| LaTeX tables (booktabs) | 4 | `.tex` |
| Executed notebook reports | 6 | `.html` |
| Statistical results | — | stdout + files |

## Prerequisites

Python 3.11+ and one of:

```bash
pip install -r requirements.txt
```

```bash
conda env create -f environment.yml
conda activate eda-benchmark
```

## Quick start

```bash
# With live Prometheus (run immediately after benchmarks):
./analysis/run-analysis.sh

# With existing data/ CSVs (Prometheus no longer required):
./analysis/run-analysis.sh --skip-export
```

## Running individual scripts

```bash
# Export Prometheus metrics to data/
python scripts/export_prometheus.py
python scripts/export_prometheus.py --start 2024-01-01T10:00:00Z --end 2024-01-01T11:00:00Z

# Statistical tests → output/tables/
python scripts/statistical_tests.py

# All 8 figures → output/figures/
python scripts/generate_charts.py

# All 5 tables → output/tables/
python scripts/generate_tables.py
```

## Running notebooks

```bash
jupyter notebook
```

Open notebooks in order `01` → `06`.  Each notebook has a narrative structure —
every code cell is preceded by a markdown cell explaining what the cell does and why.

## Running tests

```bash
pytest tests/ -v
```

## Output reference

| File | Description |
|---|---|
| `output/figures/fig01_latency_percentiles.png` | P50/P95/P99 bar chart — steady-state & spike |
| `output/figures/fig02_latency_timeseries.png` | P95 and P99 latency over time |
| `output/figures/fig03_throughput_timeseries.png` | RPS + Kafka consumer lag |
| `output/figures/fig04_resource_utilisation.png` | CPU and heap memory 2×2 grid |
| `output/figures/fig05_fault_recovery.png` | Latency under three fault scenarios |
| `output/figures/fig06_latency_cdf.png` | Empirical CDF (log x-axis) |
| `output/figures/fig07_devex_radar.png` | Developer experience radar chart |
| `output/figures/fig08_significance_heatmap.png` | Statistical summary heatmap |
| `output/tables/table01_descriptive_stats.md/.tex` | Mean, Std, P50–P99, Max per metric |
| `output/tables/table02_statistical_tests.md/.tex` | Mann-Whitney U, p-value, effect size, winner |
| `output/tables/table03_fault_summary.md/.tex` | Baseline vs fault P95 per scenario |
| `output/tables/table04_devex.md/.tex` | LOC, build/test time, image size |
| `output/tables/table05_recommendations.md` | When to choose each stack |
| `output/report/0N-*.html` | Executed Jupyter notebooks as HTML |

## Dissertation chapter mapping

| Output | Dissertation section |
|---|---|
| Figure 1–2 + Table 1–2 | Chapter 4.1 — Latency Results |
| Figure 3   + Table 1   | Chapter 4.2 — Throughput Results |
| Figure 4   + Table 1   | Chapter 4.3 — Resource Utilisation |
| Figure 5   + Table 3   | Chapter 4.4 — Fault Tolerance |
| Figure 7   + Table 4   | Chapter 4.5 — Developer Experience |
| Figure 8   + Table 2   | Chapter 5   — Discussion |
| Table 5                | Chapter 5   — Recommendations |

## Interpreting statistical results

| Symbol | Meaning |
|---|---|
| p < 0.05 | Statistically significant difference at 95% confidence |
| Cliff's δ < 0.147 | Negligible effect |
| Cliff's δ < 0.330 | Small effect |
| Cliff's δ < 0.474 | Medium effect |
| Cliff's δ ≥ 0.474 | Large effect |
| CI excludes 0 | Consistent directional difference |
| Winner | Service with lower mean (latency/CPU/memory/LOC) or higher mean (throughput/tests) |

## Adding a new metric

1. Add the PromQL query to `scripts/export_prometheus.py:export_all()`
2. Add a test pair to `scripts/statistical_tests.py`
3. Add a figure function to `scripts/generate_charts.py`
4. Add a table row to `scripts/generate_tables.py:table01_descriptive_stats()`
5. Add a notebook cell to the relevant `.ipynb`
