#!/usr/bin/env bash
set -euo pipefail

DURATION=${DURATION:-30}
OUTPUT_DIR="$(cd "$(dirname "$0")/../results" && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
TRACE_FILE="${OUTPUT_DIR}/dotnet-trace-${TIMESTAMP}.nettrace"
SPEEDSCOPE_FILE="${OUTPUT_DIR}/dotnet-trace-${TIMESTAMP}.speedscope.json"

echo "==> Resolving dotnet-service container PID..."
CONTAINER_ID=$(docker inspect --format '{{.Id}}' dotnet-service)
PID=$(docker exec dotnet-service sh -c 'pgrep -o dotnet || pgrep -o OrderService')

if [ -z "$PID" ]; then
  echo "ERROR: could not find dotnet process inside container" >&2
  exit 1
fi

echo "==> Collecting CPU + GC trace for ${DURATION}s (PID=${PID})..."
docker exec dotnet-service dotnet-trace collect \
  --process-id "$PID" \
  --duration "00:00:${DURATION}" \
  --providers "Microsoft-DotNETRuntime:0x1F:4,Microsoft-AspNetCore-Server-Kestrel:0xFF:4" \
  --output /tmp/trace.nettrace

echo "==> Copying trace from container..."
docker cp "dotnet-service:/tmp/trace.nettrace" "$TRACE_FILE"

echo "==> Converting to speedscope..."
docker exec dotnet-service dotnet-trace convert \
  --format Speedscope \
  /tmp/trace.nettrace \
  --output /tmp/trace.speedscope.json
docker cp "dotnet-service:/tmp/trace.speedscope.json" "$SPEEDSCOPE_FILE"

echo ""
echo "Trace saved:      $TRACE_FILE"
echo "Speedscope saved: $SPEEDSCOPE_FILE"
echo "Open speedscope:  https://www.speedscope.app  (drag-and-drop the .json)"
