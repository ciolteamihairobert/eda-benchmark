#!/usr/bin/env bash
# Orchestrates the full analysis pipeline.
# Run after benchmark data is collected and Prometheus is still running.
#
# Usage: ./analysis/run-analysis.sh [--skip-export]
# --skip-export: skip Prometheus export (use existing data/ CSVs)

set -euo pipefail
cd "$(dirname "$0")"

SKIP_EXPORT="${1:-}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

### Step 0 — Python environment check
python3 -c "import pandas, scipy, matplotlib, pingouin" 2>/dev/null \
  || { echo "ERROR: missing dependencies. Run: pip install -r requirements.txt"; exit 1; }

mkdir -p data output/figures output/tables output/report

### Step 1 — Export Prometheus data
if [[ "$SKIP_EXPORT" != "--skip-export" ]]; then
  log "=== Step 1/5: Exporting Prometheus metrics → data/ ==="
  python3 scripts/export_prometheus.py
  log "Export complete."
else
  log "Skipping Prometheus export (--skip-export)."
fi

### Step 2 — Statistical tests
log "=== Step 2/5: Running statistical tests ==="
python3 scripts/statistical_tests.py
log "Statistical tests complete."

### Step 3 — Generate charts
log "=== Step 3/5: Generating figures ==="
python3 scripts/generate_charts.py
log "Figures saved to output/figures/."

### Step 4 — Generate tables
log "=== Step 4/5: Generating tables ==="
python3 scripts/generate_tables.py
log "Tables saved to output/tables/."

### Step 5 — Execute notebooks → HTML reports
log "=== Step 5/5: Executing notebooks → HTML ==="
for nb in notebooks/*.ipynb; do
  name=$(basename "$nb" .ipynb)
  log "  Running $name ..."
  jupyter nbconvert --to html \
    --execute "$nb" \
    --output "../output/report/${name}.html" \
    --ExecutePreprocessor.timeout=300 \
    2>/dev/null \
    && log "  ✓ $name" \
    || log "  ✗ $name (check data/ files exist)"
done

### Summary
log ""
log "=== Analysis complete ==="
PNG_COUNT=$(ls output/figures/*.png 2>/dev/null | wc -l)
MD_COUNT=$(ls output/tables/*.md   2>/dev/null | wc -l)
TEX_COUNT=$(ls output/tables/*.tex 2>/dev/null | wc -l)
HTML_COUNT=$(ls output/report/*.html 2>/dev/null | wc -l)
log "Figures:  ${PNG_COUNT} PNG files"
log "Tables:   ${MD_COUNT} Markdown files"
log "Tables:   ${TEX_COUNT} LaTeX files"
log "Reports:  ${HTML_COUNT} HTML notebooks"
log ""
log "Next: copy output/ into docs/chapters/ for dissertation write-up (P6)"
