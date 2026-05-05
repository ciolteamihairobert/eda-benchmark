#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="$(cd "$(dirname "$0")/../results" && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT="${OUTPUT_DIR}/devex-${TIMESTAMP}.txt"

DOTNET_SRC="$(cd "$(dirname "$0")/../../services/dotnet" && pwd)"
GO_SRC="$(cd "$(dirname "$0")/../../services/go" && pwd)"

{
echo "=== Developer Experience Metrics ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

echo "--- Lines of Source Code ---"
echo ".NET (*.cs, excluding tests):"
find "$DOTNET_SRC/src" -name "*.cs" | xargs wc -l 2>/dev/null | tail -1 | awk '{print "  Total: " $1}'

echo ".NET tests (*.cs):"
find "$DOTNET_SRC/tests" -name "*.cs" | xargs wc -l 2>/dev/null | tail -1 | awk '{print "  Total: " $1}'

echo "Go (*.go, excluding tests):"
find "$GO_SRC" -name "*.go" ! -name "*_test.go" | xargs wc -l 2>/dev/null | tail -1 | awk '{print "  Total: " $1}'

echo "Go tests (*_test.go):"
find "$GO_SRC" -name "*_test.go" | xargs wc -l 2>/dev/null | tail -1 | awk '{print "  Total: " $1}'
echo ""

echo "--- File Counts ---"
echo ".NET source files: $(find "$DOTNET_SRC/src" -name "*.cs" | wc -l)"
echo ".NET test files:   $(find "$DOTNET_SRC/tests" -name "*.cs" | wc -l)"
echo "Go source files:   $(find "$GO_SRC" -name "*.go" ! -name "*_test.go" | wc -l)"
echo "Go test files:     $(find "$GO_SRC" -name "*_test.go" | wc -l)"
echo ""

echo "--- Build Times ---"
echo ".NET build:"
time (cd "$DOTNET_SRC" && dotnet build -c Release -v q 2>&1 | tail -3) 2>&1

echo ""
echo "Go build:"
time (cd "$GO_SRC" && go build ./... 2>&1) 2>&1
echo ""

echo "--- Test Execution Times ---"
echo ".NET tests:"
time (cd "$DOTNET_SRC" && dotnet test -v q 2>&1 | tail -5) 2>&1

echo ""
echo "Go tests:"
time (cd "$GO_SRC" && go test ./... 2>&1) 2>&1
echo ""

echo "--- Dependency Counts ---"
echo ".NET direct packages:"
grep -c '<PackageReference' "$DOTNET_SRC/src/OrderService.Api/OrderService.Api.csproj" || echo "  n/a"

echo "Go direct modules:"
grep -v '// indirect' "$GO_SRC/go.mod" | grep -c '^\s' || echo "  n/a"
echo ""

echo "--- Docker Image Sizes ---"
docker images --format "{{.Repository}}:{{.Tag}}\t{{.Size}}" | grep -E "dotnet-service|go-service" || echo "  (images not built yet)"

} | tee "$REPORT"

echo ""
echo "Report saved: $REPORT"
