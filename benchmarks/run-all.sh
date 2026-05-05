#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

DOTNET_URL=${DOTNET_URL:-http://localhost:8080}
GO_URL=${GO_URL:-http://localhost:8081}
PROM_RW_URL=${PROM_RW_URL:-http://localhost:9090/api/v1/write}

K6=${K6:-k6}

mkdir -p "$RESULTS_DIR"

run_k6() {
  local name="$1"
  local script="$2"
  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  Running: ${name}"
  echo "════════════════════════════════════════════════════════"
  "$K6" run \
    --out "experimental-prometheus-rw=${PROM_RW_URL}" \
    -e DOTNET_URL="$DOTNET_URL" \
    -e GO_URL="$GO_URL" \
    -e PROM_RW_URL="$PROM_RW_URL" \
    "$script"
}

echo "Starting full benchmark suite — ${TIMESTAMP}"
echo "  .NET:       ${DOTNET_URL}"
echo "  Go:         ${GO_URL}"
echo "  Prometheus: ${PROM_RW_URL}"

run_k6 "Steady-State"     "${SCRIPT_DIR}/steady-state/steady-state.js"
run_k6 "Spike"            "${SCRIPT_DIR}/spike/spike.js"
run_k6 "Network Delay"    "${SCRIPT_DIR}/fault/network-delay.js"
run_k6 "Consumer Restart" "${SCRIPT_DIR}/fault/consumer-restart.js"
run_k6 "Broker Outage"    "${SCRIPT_DIR}/fault/broker-outage.js"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  All benchmarks complete."
echo "  Results written to: ${RESULTS_DIR}/"
echo "  Files:"
ls -1 "${RESULTS_DIR}"/*.json 2>/dev/null | sed 's/^/    /' || echo "    (none found)"
echo "════════════════════════════════════════════════════════"
