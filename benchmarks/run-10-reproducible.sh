#!/usr/bin/env bash
# 10-run reproducible benchmark collection.
# Each run: warm-up (30s) -> steady-state (~5min) -> spike (~2.5min)
#           -> fault-delay (200ms, ~1.5min) -> meta.json -> 90s cooldown
# Final step: single Prometheus export covering the whole experiment window.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
INFRA_DIR="${REPO_ROOT}/infrastructure"

DOTNET_URL="${DOTNET_URL:-http://localhost:8080}"
GO_URL="${GO_URL:-http://localhost:8081}"
PROM_RW_URL="${PROM_RW_URL:-http://localhost:9090/api/v1/write}"
PROM_URL="${PROM_URL:-http://localhost:9090}"

TOTAL_RUNS=10
COOLDOWN_S=90
FAULT_DELAY_MS=200

K6="${K6:-k6}"
PYTHON="${PYTHON:-/c/tmp/eda-venv/Scripts/python.exe}"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }
hr()  { echo "------------------------------------------------------------"; }

# ── helpers ──────────────────────────────────────────────────────────────────

wait_healthy() {
  local name="$1"
  local url="$2"
  local max=30 i=0
  log "Waiting for ${name} to be healthy..."
  until curl -sf "${url}" > /dev/null 2>&1; do
    i=$((i+1))
    if [ $i -ge $max ]; then
      log "ERROR: ${name} did not become healthy in time"
      exit 1
    fi
    sleep 2
  done
  log "${name} is healthy"
}

run_k6() {
  local label="$1"
  local script="$2"
  local outfile="$3"
  log "k6: ${label}"
  "$K6" run \
    --out "experimental-prometheus-rw=${PROM_RW_URL}" \
    -e DOTNET_URL="${DOTNET_URL}" \
    -e GO_URL="${GO_URL}" \
    -e PROM_RW_URL="${PROM_RW_URL}" \
    --summary-export "${outfile}" \
    "${script}" || true   # don't abort run on threshold breach
}

inject_fault() {
  log "Injecting fault: FAULT_DELAY_MS=${FAULT_DELAY_MS}"
  cd "${INFRA_DIR}"
  FAULT_DELAY_MS="${FAULT_DELAY_MS}" FAULT_FAIL_RATE="0.0" \
    docker compose up -d --force-recreate --no-deps dotnet-service go-service 2>&1 | tail -5
  wait_healthy ".NET (fault)" "${DOTNET_URL}/health"
  wait_healthy "Go (fault)"   "${GO_URL}/health"
}

remove_fault() {
  log "Removing fault"
  cd "${INFRA_DIR}"
  FAULT_DELAY_MS=0 FAULT_FAIL_RATE="0.0" \
    docker compose up -d --force-recreate --no-deps dotnet-service go-service 2>&1 | tail -5
  wait_healthy ".NET (normal)" "${DOTNET_URL}/health"
  wait_healthy "Go (normal)"   "${GO_URL}/health"
}

# ── main loop ─────────────────────────────────────────────────────────────────

EXPERIMENT_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EXPERIMENT_START_EPOCH=$(date +%s)

log "Starting 10-run reproducible benchmark collection"
log "  .NET:       ${DOTNET_URL}"
log "  Go:         ${GO_URL}"
log "  Prometheus: ${PROM_RW_URL}"
log "  Python:     ${PYTHON}"
hr

wait_healthy ".NET" "${DOTNET_URL}/health"
wait_healthy "Go"   "${GO_URL}/health"

for run_num in $(seq 1 ${TOTAL_RUNS}); do
  RUN_ID=$(printf "run-%02d" ${run_num})
  RUN_DIR="${RESULTS_DIR}/${RUN_ID}"
  K6_DIR="${RUN_DIR}/k6"

  mkdir -p "${K6_DIR}"

  hr
  log "=== ${RUN_ID} of ${TOTAL_RUNS} ==="
  RUN_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  RUN_START_EPOCH=$(date +%s)

  # ── Warm-up (30s, low VUs, discard results) ─────────────────────────────────
  log "Warm-up: 30s at 5 VUs"
  "$K6" run \
    -e DOTNET_URL="${DOTNET_URL}" \
    -e GO_URL="${GO_URL}" \
    --vus 5 --duration 30s --no-summary \
    "${SCRIPT_DIR}/steady-state/steady-state.js" 2>&1 | grep -vE "^$" | tail -3 || true
  log "Warm-up done"

  # ── Steady-state (~5 min ramp-up/down) ──────────────────────────────────────
  run_k6 "steady-state" \
    "${SCRIPT_DIR}/steady-state/steady-state.js" \
    "${K6_DIR}/steady-state-summary.json"

  # ── Spike (~2.5 min) ────────────────────────────────────────────────────────
  run_k6 "spike" \
    "${SCRIPT_DIR}/spike/spike.js" \
    "${K6_DIR}/spike-summary.json"

  # ── Fault: 200ms processing delay (~1.5 min) ────────────────────────────────
  inject_fault
  run_k6 "fault-delay" \
    "${SCRIPT_DIR}/fault/network-delay.js" \
    "${K6_DIR}/fault-delay-summary.json"
  remove_fault

  RUN_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  DURATION_S=$(( $(date +%s) - RUN_START_EPOCH ))

  # ── meta.json ────────────────────────────────────────────────────────────────
  cat > "${RUN_DIR}/meta.json" <<METAJSON
{
  "run": ${run_num},
  "run_id": "${RUN_ID}",
  "started_at": "${RUN_START}",
  "finished_at": "${RUN_END}",
  "duration_s": ${DURATION_S},
  "dotnet_url": "${DOTNET_URL}",
  "go_url": "${GO_URL}",
  "fault_delay_ms": ${FAULT_DELAY_MS},
  "k6_version": "$(k6 version | head -1)",
  "phases": ["warmup-30s", "steady-state", "spike", "fault-delay-${FAULT_DELAY_MS}ms"]
}
METAJSON

  log "${RUN_ID} complete in ${DURATION_S}s — cooldown ${COOLDOWN_S}s..."
  sleep "${COOLDOWN_S}"
done

# ── Final Prometheus export covering the whole experiment window ──────────────
hr
EXPERIMENT_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EXPERIMENT_SECS=$(( $(date +%s) - EXPERIMENT_START_EPOCH ))
log "Exporting aggregate Prometheus data..."
log "  Window: ${EXPERIMENT_START} to ${EXPERIMENT_END} (${EXPERIMENT_SECS}s)"

cd "${REPO_ROOT}/analysis"
"${PYTHON}" scripts/export_prometheus.py \
  --prometheus "${PROM_URL}" \
  --start "${EXPERIMENT_START}" \
  --end   "${EXPERIMENT_END}" \
  --step  15 \
  2>&1 | tee "${RESULTS_DIR}/prometheus-export.log"

hr
log "All ${TOTAL_RUNS} runs complete."
log "Results directory:"
ls "${RESULTS_DIR}/"
