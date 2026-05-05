#!/usr/bin/env bash
set -euo pipefail

GO_URL=${GO_URL:-http://localhost:8081}
OUTPUT_DIR="$(cd "$(dirname "$0")/../results" && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
HEAP_FILE="${OUTPUT_DIR}/go-heap-${TIMESTAMP}.pprof"
GOROUTINE_FILE="${OUTPUT_DIR}/go-goroutines-${TIMESTAMP}.txt"
SVG_FILE="${OUTPUT_DIR}/go-heap-${TIMESTAMP}.svg"

echo "==> Collecting heap profile from ${GO_URL}..."
curl -sf "${GO_URL}/debug/pprof/heap" -o "$HEAP_FILE"

echo "==> Collecting goroutine dump..."
curl -sf "${GO_URL}/debug/pprof/goroutine?debug=1" -o "$GOROUTINE_FILE"

echo "==> Generating heap flamegraph SVG..."
go tool pprof -svg "$HEAP_FILE" > "$SVG_FILE"

GOROUTINE_COUNT=$(grep -c '^goroutine ' "$GOROUTINE_FILE" || true)

echo ""
echo "Heap profile saved:     $HEAP_FILE"
echo "Heap flamegraph saved:  $SVG_FILE"
echo "Goroutine dump saved:   $GOROUTINE_FILE"
echo "Active goroutines:      ${GOROUTINE_COUNT}"
echo ""
echo "Interactive exploration:"
echo "  go tool pprof -http=:6060 $HEAP_FILE"
