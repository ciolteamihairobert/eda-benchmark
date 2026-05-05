#!/usr/bin/env bash
set -euo pipefail

DURATION=${DURATION:-30}
GO_URL=${GO_URL:-http://localhost:8081}
OUTPUT_DIR="$(cd "$(dirname "$0")/../results" && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
PROFILE_FILE="${OUTPUT_DIR}/go-cpu-${TIMESTAMP}.pprof"
SVG_FILE="${OUTPUT_DIR}/go-cpu-${TIMESTAMP}.svg"

echo "==> Collecting CPU profile for ${DURATION}s from ${GO_URL}..."
curl -sf "${GO_URL}/debug/pprof/profile?seconds=${DURATION}" -o "$PROFILE_FILE"

echo "==> Generating flamegraph SVG..."
go tool pprof -svg "$PROFILE_FILE" > "$SVG_FILE"

echo ""
echo "Profile saved:   $PROFILE_FILE"
echo "Flamegraph saved: $SVG_FILE"
echo ""
echo "Interactive exploration:"
echo "  go tool pprof -http=:6060 $PROFILE_FILE"
