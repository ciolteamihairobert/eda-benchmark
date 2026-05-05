# EDA Benchmark — Complete Operational Guide

> Follow this guide top to bottom on a fresh machine.  
> If anything fails, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Repository Setup](#2-repository-setup)
3. [Infrastructure (P1)](#3-infrastructure-p1)
4. [.NET Service (P2)](#4-net-service-p2)
5. [Go Service (P3)](#5-go-service-p3)
6. [Verifying Both Services](#6-verifying-both-services)
7. [Running the Benchmark Suite (P4)](#7-running-the-benchmark-suite-p4)
8. [Collecting and Analysing Results (P5)](#8-collecting-and-analysing-results-p5)
9. [Viewing Results in Grafana](#9-viewing-results-in-grafana)
10. [Fault Injection Scenarios](#10-fault-injection-scenarios)
11. [Profiling](#11-profiling)
12. [Full Automated Run](#12-full-automated-run)
13. [Resetting the Environment](#13-resetting-the-environment)
14. [CI/CD — GitHub Actions](#14-cicd--github-actions)

---

## 1. Prerequisites

### 1.1 Required tools

| Tool             | Min version | Install                                                    | Verify                    |
|------------------|-------------|------------------------------------------------------------|---------------------------|
| Docker Desktop   | 24.x        | https://docs.docker.com/get-docker/                        | `docker --version`        |
| Docker Compose   | 2.24        | Bundled with Docker Desktop                                | `docker compose version`  |
| Git              | 2.x         | https://git-scm.com                                        | `git --version`           |
| k6               | 0.50+       | `brew install k6` / `choco install k6`                     | `k6 version`              |
| .NET SDK         | 8.0         | https://dotnet.microsoft.com/download                      | `dotnet --version`        |
| Go               | 1.22        | https://go.dev/dl/                                         | `go version`              |
| Python           | 3.11        | https://www.python.org/downloads/                          | `python3 --version`       |
| dotnet-trace     | latest      | `dotnet tool install -g dotnet-trace`                      | `dotnet-trace --version`  |
| dotnet-counters  | latest      | `dotnet tool install -g dotnet-counters`                   | `dotnet-counters --version` |
| cloc             | any         | `brew install cloc` / `apt install cloc`                   | `cloc --version`          |
| graphviz         | any         | `brew install graphviz` / `apt install graphviz`           | `dot -V`                  |

> **Windows note:** all `make` commands require [GNU Make for Windows](https://gnuwin32.sourceforge.net/packages/make.htm) or Git Bash.  
> PowerShell equivalents are shown where they differ.

### 1.2 Hardware recommendations

| | Minimum | Recommended |
|---|---|---|
| CPU cores | 4 | 8 |
| RAM | 8 GB | 16 GB |
| Free disk | 10 GB | 20 GB |

Docker alone (Kafka + Zookeeper + Prometheus + Grafana + both services) requires approximately 4 GB RAM.  
Running k6 simultaneously adds ~500 MB.

### 1.3 Ports used

| Port | Service | URL |
|------|---------|-----|
| 2181 | Zookeeper | Internal only |
| 9092 | Kafka | `localhost:9092` (host access) |
| 9101 | Kafka JMX | Internal |
| 9308 | kafka-exporter | Prometheus scrape target |
| 9090 | Prometheus | http://localhost:9090 |
| 3000 | Grafana | http://localhost:3000 |
| 8080 | .NET service | http://localhost:8080 |
| 8081 | Go service | http://localhost:8081 |
| 8081 | Go pprof | http://localhost:8081/debug/pprof/ |

Check nothing is already using these ports before starting:

```bash
lsof -i :9092 -i :9090 -i :3000 -i :8080 -i :8081
```

If any port is in use, see [port conflicts](TROUBLESHOOTING.md#-docker-error-bind-for-00009092-failed-port-is-already-allocated).

---

## 2. Repository Setup

### 2.1 Clone

```bash
git clone https://github.com/YOUR_USERNAME/eda-benchmark.git
cd eda-benchmark
```

### 2.2 Project structure

```
eda-benchmark/
├── infrastructure/          Docker Compose stack, Makefile, Prometheus config, Grafana provisioning, k6 baseline
│   ├── docker-compose.yml
│   ├── Makefile
│   ├── k6/                  Original P1 baseline k6 script
│   └── monitoring/          Prometheus + Grafana config and dashboards
├── services/
│   ├── dotnet/              ASP.NET Core 8 + MediatR service (P2)
│   └── go/                  Go 1.22 goroutines + kafka-go service (P3)
├── benchmarks/              k6 benchmark scripts, profiling scripts, devex measure (P4)
│   ├── steady-state/
│   ├── spike/
│   ├── fault/
│   ├── profiling/
│   ├── devex/
│   └── results/             Output CSVs and profile files (git-ignored)
├── analysis/                Python statistical analysis pipeline (P5)
│   ├── scripts/
│   ├── notebooks/
│   ├── data/                Prometheus exports land here (git-ignored)
│   └── output/              Figures, tables, HTML reports (git-ignored)
└── docs/                    This guide + TROUBLESHOOTING.md
```

### 2.3 Environment variables reference

| Variable | Service | Default | Description |
|---|---|---|---|
| `Kafka__BootstrapServers` | .NET | `localhost:9092` | Kafka broker address (local run) |
| `Fault__DelayMs` | .NET | `0` | Artificial processing delay (ms) |
| `Fault__FailRate` | .NET | `0.0` | Fraction of orders to fail (0.0–1.0) |
| `KAFKA_BOOTSTRAP` | Go | `localhost:9092` | Kafka broker address (local run) |
| `FAULT_DELAY_MS` | Go | `0` | Artificial processing delay (ms) |
| `FAULT_FAIL_RATE` | Go | `0.0` | Fraction of orders to fail (0.0–1.0) |
| `WORKER_COUNT` | Go | `10` | Goroutine worker pool size |
| `PROMETHEUS_URL` | Analysis | `http://localhost:9090` | Prometheus base URL |
| `DOTNET_URL` | k6 / Make | `http://localhost:8080` | .NET service base URL |
| `GO_URL` | k6 / Make | `http://localhost:8081` | Go service base URL |
| `PROM_RW_URL` | k6 / Make | `http://localhost:9090/api/v1/write` | Prometheus remote-write endpoint |

> In Docker, both services use `kafka:29092` (container-to-container listener). The values above are for local (`dotnet run` / `go run`) execution only.

---

## 3. Infrastructure (P1)

### 3.1 Start the stack

```bash
cd infrastructure
make up
```

Expected output:
```
[+] Building ...
[+] Running 6/6
 ✓ Container zookeeper       Started
 ✓ Container kafka            Started
 ✓ Container kafka-init       Started
 ✓ Container kafka-exporter   Started
 ✓ Container prometheus       Started
 ✓ Container grafana          Started

Infrastructure is starting. Run 'make verify-env' in ~30s to check readiness.
```

### 3.2 What `make up` starts

Containers start in this order:

1. **zookeeper** — Kafka's coordination service. Healthcheck: `echo ruok | nc localhost 2181`.
2. **kafka** — Single-broker Kafka 7.6. Two listeners: `kafka:29092` (container-to-container) and `localhost:9092` (host). Healthcheck: `kafka-broker-api-versions`.
3. **kafka-init** — One-shot container that creates three topics: `orders.placed` (3 partitions), `orders.processed` (3 partitions), `orders.failed` (1 partition). Exits 0 on success.
4. **kafka-exporter** — Exposes Kafka consumer group lag metrics on `:9308` for Prometheus to scrape.
5. **prometheus** — Scrapes kafka-exporter, dotnet-service, and go-service every 10s. Remote-write receiver enabled for k6.
6. **grafana** — Pre-provisioned with Prometheus datasource and the "EDA Benchmark Overview" dashboard.

> Kafka takes 30–40 seconds to become healthy. Wait before running `make verify-env`.

### 3.3 Verify infrastructure

```bash
make verify-env
```

Expected output at this stage (services not yet running):
```
==========================================
 EDA Benchmark — service health check
==========================================
Kafka:          OK
Prometheus:     OK  →  http://localhost:9090
Grafana:        OK  →  http://localhost:3000  (admin / benchmark)
dotnet-service: not reachable — start P2 first
go-service:     not reachable — start P3 first
==========================================
```

If Kafka shows `UNREACHABLE`, wait 30 more seconds and retry. See [Kafka not starting](TROUBLESHOOTING.md#-kafka-not-starting--broker-may-not-be-available).

### 3.4 Verify Kafka topics

```bash
make kafka-topics
```

Expected:
```
orders.failed
orders.placed
orders.processed
```

If the list is empty, see [Kafka topics not created](TROUBLESHOOTING.md#-kafka-topics-not-created).

### 3.5 Open Grafana

- URL: http://localhost:3000
- Username: `admin`
- Password: `benchmark`
- Navigate to **Dashboards → EDA Benchmark Overview**

The dashboard will show "No data" until services are running — that is expected.

---

## 4. .NET Service (P2)

Choose **Option A** (local) for development and debugging, **Option B** (Docker) for benchmarking.

### 4.1 Option A — Run locally

Requires .NET SDK 8 and infrastructure running (Section 3).

```bash
cd services/dotnet
dotnet restore
dotnet build -c Release
```

**Mac/Linux:**
```bash
Kafka__BootstrapServers=localhost:9092 \
  dotnet run --project src/OrderService.Api --configuration Release
```

**Windows (PowerShell):**
```powershell
$env:Kafka__BootstrapServers = "localhost:9092"
dotnet run --project src\OrderService.Api --configuration Release
```

Expected output:
```
[10:00:01 INF] Starting up
[10:00:01 INF] Kafka producer initialised bootstrap=localhost:9092
[10:00:01 INF] Kafka consumer starting group=dotnet-order-service
[10:00:01 INF] Now listening on http://[::]:8080
```

### 4.2 Option B — Run in Docker (recommended for benchmarking)

The `dotnet-service` block is already present in `infrastructure/docker-compose.yml`. It starts automatically with `make up` once the image is built:

```bash
cd infrastructure
make up   # builds and starts dotnet-service along with the rest of the stack
```

### 4.3 Verify the .NET service

```bash
curl http://localhost:8080/health
```
Expected: `{"status":"ok","timestamp":"2024-01-01T10:00:00Z"}`

```bash
curl -s -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{
    "orderId": "test-001",
    "customerId": "cust-1",
    "items": [{"sku": "SKU-001", "quantity": 1, "price": 9.99}],
    "timestamp": "2024-01-01T00:00:00Z"
  }'
```
Expected: HTTP 202 — `{"orderId":"test-001","status":"accepted","acceptedAt":"..."}`

```bash
curl -s http://localhost:8080/metrics | head -20
```
Expected: Prometheus text format beginning with `# HELP orders_received_total ...`

### 4.4 Run .NET tests

```bash
cd services/dotnet
dotnet test --logger "console;verbosity=normal"
```

Expected:
```
Passed!  - Failed: 0, Passed: 5, Skipped: 0, Total: 5
```

---

## 5. Go Service (P3)

### 5.1 Option A — Run locally

```bash
cd services/go
go mod tidy
go build ./...
```

**Mac/Linux:**
```bash
KAFKA_BOOTSTRAP=localhost:9092 go run ./cmd/server
```

**Windows (PowerShell):**
```powershell
$env:KAFKA_BOOTSTRAP = "localhost:9092"
go run ./cmd/server
```

Expected output (structured JSON logs):
```json
{"level":"info","ts":"...","msg":"worker pool started","workers":10}
{"level":"info","ts":"...","msg":"server started","addr":":8081"}
```

### 5.2 Option B — Run in Docker (recommended for benchmarking)

The `go-service` block is already in `infrastructure/docker-compose.yml`:

```bash
cd infrastructure
make up   # builds and starts go-service along with the rest of the stack
```

### 5.3 Verify the Go service

```bash
curl http://localhost:8081/health
```
Expected: `{"status":"ok","timestamp":"..."}`

```bash
curl -s -X POST http://localhost:8081/orders \
  -H "Content-Type: application/json" \
  -d '{
    "orderId": "test-go-001",
    "customerId": "cust-1",
    "items": [{"sku": "SKU-001", "quantity": 1, "price": 9.99}],
    "timestamp": "2024-01-01T00:00:00Z"
  }'
```
Expected: HTTP 202 — `{"orderId":"test-go-001","status":"accepted","acceptedAt":"..."}`

```bash
curl -s http://localhost:8081/metrics | head -20
```
Expected: Prometheus text format with `orders_received_total`, `orders_processed_total`, etc.

### 5.4 Run Go tests

```bash
cd services/go
go test ./... -v
```

Expected: all tests end with `PASS`.

---

## 6. Verifying Both Services

### 6.1 Full health check

```bash
cd infrastructure
make verify-env
```

All five lines should now show `OK`:
```
==========================================
 EDA Benchmark — service health check
==========================================
Kafka:          OK
Prometheus:     OK  →  http://localhost:9090
Grafana:        OK  →  http://localhost:3000  (admin / benchmark)
dotnet-service: OK  →  http://localhost:8080
go-service:     OK  →  http://localhost:8081
==========================================
```

### 6.2 Confirm Prometheus is scraping both services

Open http://localhost:9090/targets — `dotnet-service` and `go-service` should both show **State = UP**.

If either shows DOWN, see [Prometheus shows service as DOWN](TROUBLESHOOTING.md#-prometheus-shows-dotnet-service-or-go-service-as-down).

### 6.3 Send warm-up traffic and confirm Grafana updates

```bash
for i in $(seq 1 10); do
  curl -s -X POST http://localhost:8080/orders \
    -H "Content-Type: application/json" \
    -d "{\"orderId\":\"warmup-dn-$i\",\"customerId\":\"cust-$i\",
         \"items\":[{\"sku\":\"SKU-001\",\"quantity\":1,\"price\":9.99}],
         \"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > /dev/null
  curl -s -X POST http://localhost:8081/orders \
    -H "Content-Type: application/json" \
    -d "{\"orderId\":\"warmup-go-$i\",\"customerId\":\"cust-$i\",
         \"items\":[{\"sku\":\"SKU-001\",\"quantity\":1,\"price\":9.99}],
         \"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > /dev/null
done
```

Refresh Grafana — the **Orders Received** and **Kafka Messages/sec** counters should increment.

---

## 7. Running the Benchmark Suite (P4)

> Always run `make verify-env` before starting any benchmark to confirm all services are healthy.

All `make` commands in this section run from the **repo root** or the `infrastructure/` directory. The Makefile auto-detects the path.

### 7.1 Steady-state benchmark (~10 min)

```bash
cd infrastructure
make bench-steady
```

VU profile: 0 → 10 → 50 → 100 → 50 → 0 over 5 minutes.

**What to watch in Grafana:**
- **k6 P95 Latency** panel: both service lines should be stable, not climbing
- **k6 Requests/sec** panel: should ramp up in sync with the VU stages
- **Kafka Consumer Lag** panel: should remain near 0

Output written to: `benchmarks/results/steady-state-summary.json`

A results table is printed to stdout:
```
┌──────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Service      │   P50 ms │   P95 ms │   P99 ms │      RPS │ Err rate │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ .NET         │     xx.x │     xx.x │     xx.x │     xx.x │    0.00% │
│ Go           │     xx.x │     xx.x │     xx.x │     xx.x │    0.00% │
└──────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

### 7.2 Spike benchmark (~5 min)

```bash
make bench-spike
```

VU profile: 0 → 10 → **200** → 10 → 0 (sudden burst).

**What to watch:** latency spike when VUs jump to 200; how quickly each service recovers when VUs drop back.

### 7.3 Fault: network delay (~3 min)

**Step 1** — Inject delay by editing `infrastructure/docker-compose.yml`:

```yaml
go-service:
  environment:
    FAULT_DELAY_MS: "200"      # was "0"

dotnet-service:
  environment:
    Fault__DelayMs: "200"      # was "0"
```

**Step 2** — Recreate the service containers to pick up the new env vars:

```bash
docker compose -f infrastructure/docker-compose.yml up -d \
  --force-recreate dotnet-service go-service
```

**Step 3** — Run the benchmark:

```bash
make bench-fault-delay
```

**Step 4** — Restore normal operation (reset env vars back to `"0"`, then):

```bash
docker compose -f infrastructure/docker-compose.yml up -d \
  --force-recreate dotnet-service go-service
```

### 7.4 Fault: consumer restart (~5 min)

**Terminal 1** — start the benchmark and let it reach steady load:
```bash
make bench-fault-restart
```

**Terminal 2** — wait 90 seconds, then restart both consumers:
```bash
cd infrastructure && make fault-consumer-restart
```

Watch the **Kafka Consumer Lag** panel spike, then recover as the consumer groups rebalance.

### 7.5 Fault: broker outage (~4 min)

**Terminal 1** — start the benchmark:
```bash
make bench-fault-outage
```

**Terminal 2** — wait 60 seconds, stop Kafka, wait 60 seconds, restart:
```bash
cd infrastructure
make fault-broker-stop
# wait 60 seconds
make fault-broker-start
```

Watch error rates spike then return to 0 in Grafana.

### 7.6 Run the full suite automatically (~35 min)

```bash
./benchmarks/run-all.sh
```

Runs all five scenarios in sequence. Progress is printed with timestamps:
```
[10:00:00] Running: Steady-State
...
[10:10:30] Running: Spike
...
[10:42:00] All benchmarks complete.
  Results written to: benchmarks/results/
```

> If any scenario fails, see [k6 errors](TROUBLESHOOTING.md#-k6-error-econnrefused-localhost8080).

---

## 8. Collecting and Analysing Results (P5)

### 8.1 Install Python dependencies

```bash
cd analysis
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Verify:
```bash
python3 -c "import pandas, scipy, matplotlib, pingouin; print('OK')"
```

### 8.2 Export Prometheus metrics to CSV

Run this **while Prometheus is still running** (within its 7-day retention window).

```bash
python3 scripts/export_prometheus.py
```

Expected output:
```
Exporting metrics: 2024-01-15T08:00:00+00:00 → 2024-01-15T10:00:00+00:00
Prometheus: http://localhost:9090
Output:     .../analysis/data

Exported latency_p50_dotnet.csv (720 rows)
Exported latency_p50_go.csv (720 rows)
...
Exported orders_failed_go.csv (720 rows)

Export complete.
```

If benchmarks ran more than 2 hours ago, specify the time range explicitly:
```bash
python3 scripts/export_prometheus.py \
  --start 2024-01-15T10:00:00Z \
  --end   2024-01-15T12:00:00Z
```

If `data/` is still empty after export, see [analysis/data/ is empty](TROUBLESHOOTING.md#-analysisdata-is-empty-after-export).

### 8.3 Run the full analysis pipeline

```bash
./run-analysis.sh
```

Or step by step:
```bash
python3 scripts/statistical_tests.py    # Mann-Whitney U results → stdout + output/tables/
python3 scripts/generate_charts.py      # 8 figures → output/figures/
python3 scripts/generate_tables.py      # 5 tables (.md + .tex) → output/tables/
```

Convert a single notebook to HTML:
```bash
jupyter nbconvert --execute --to html \
  notebooks/02-latency-analysis.ipynb \
  --output output/report/02-latency-analysis.html
```

### 8.4 Output locations

| Path | Contents |
|---|---|
| `analysis/output/figures/` | 8 PNG (300 dpi) + 8 PDF figures |
| `analysis/output/tables/` | 5 Markdown + 5 LaTeX (booktabs) tables |
| `analysis/output/report/` | 6 HTML executed notebook reports |

### 8.5 Run analysis unit tests

```bash
pytest analysis/tests/ -v
```

Expected: 8 tests, all `PASSED`.

---

## 9. Viewing Results in Grafana

### 9.1 Dashboard panels

Open http://localhost:3000 → **EDA Benchmark Overview**.

| Panel | What it shows |
|---|---|
| Orders Received (counter) | Cumulative orders accepted by each service |
| Orders Processed (counter) | Orders successfully published to Kafka |
| Orders Failed (counter) | Orders that hit the fault-injection error path |
| k6 P95 Latency (gauge) | Real-time P95 from k6 remote-write |
| k6 Requests/sec | Request throughput per service |
| Kafka Consumer Lag | Messages queued but not yet consumed per group |
| CPU Usage | `process_cpu_seconds_total` rate per service |
| Heap Memory | `.NET` GC heap / Go `heap_inuse_bytes` |

### 9.2 Annotating benchmark runs

Mark when each benchmark starts for clean screenshot windows:

```bash
curl -s -X POST http://localhost:3000/api/annotations \
  -H "Content-Type: application/json" \
  -u admin:benchmark \
  -d '{"text":"steady-state start","tags":["benchmark"]}'
```

```bash
curl -s -X POST http://localhost:3000/api/annotations \
  -H "Content-Type: application/json" \
  -u admin:benchmark \
  -d '{"text":"steady-state end","tags":["benchmark"]}'
```

Annotations appear as vertical lines on all time-series panels.

### 9.3 Exporting screenshots for the dissertation

1. In any Grafana panel, click the panel title → **Share** → **Direct link rendered image**
2. Or use the top-right **Share dashboard** → **Export** → **Save to file** (PNG)
3. Set the time range to `benchmark_start − 2 min` → `benchmark_end + 2 min` for clean framing

### 9.4 Adjusting the time range

Use the top-right time picker. For a 10-minute steady-state run that ended at 10:42:
- From: `10:30:00`
- To: `10:44:00`

Zoom into specific events (e.g. the spike peak) using click-and-drag on any panel.

---

## 10. Fault Injection Scenarios

| Scenario | How injected | Make target | Expected behaviour |
|---|---|---|---|
| Network delay | `FAULT_DELAY_MS=N` env var (edit docker-compose.yml) | See Section 7.3 | P95 latency rises by ~N ms |
| High fail rate | `FAULT_FAIL_RATE=0.5` env var (edit docker-compose.yml) | See Section 7.3 | ~50% orders routed to `orders.failed` |
| Consumer restart | `docker compose restart` | `make fault-consumer-restart` | Rebalance, lag spike, recovery |
| Broker stop | `docker compose stop kafka` | `make fault-broker-stop` | 5xx errors until broker returns |

### Injecting and verifying each fault

**Network delay**
```bash
# 1. Edit infrastructure/docker-compose.yml — set FAULT_DELAY_MS: "200"
# 2. Recreate services
docker compose -f infrastructure/docker-compose.yml up -d --force-recreate dotnet-service go-service
# 3. Verify delay is active
curl -w "\nTotal: %{time_total}s\n" -s -o /dev/null \
  -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"orderId":"delay-test","customerId":"c","items":[{"sku":"S","quantity":1,"price":1}],"timestamp":"2024-01-01T00:00:00Z"}'
# 4. Restore
# Edit docker-compose.yml back to FAULT_DELAY_MS: "0", then:
docker compose -f infrastructure/docker-compose.yml up -d --force-recreate dotnet-service go-service
```

**Consumer restart**
```bash
# Watch Grafana consumer lag panel, then:
cd infrastructure && make fault-consumer-restart
# Verify recovery: lag returns to 0 within ~15s
```

**Broker outage**
```bash
cd infrastructure
make fault-broker-stop
# Verify: curl http://localhost:8080/health returns 200 but orders return 500
# Restore:
make fault-broker-start
# Verify: orders return 202 again
curl -s -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"orderId":"recovery-test","customerId":"c","items":[{"sku":"S","quantity":1,"price":1}],"timestamp":"2024-01-01T00:00:00Z"}'
```

---

## 11. Profiling

Run profiling **during** a benchmark (while load is active) for meaningful results.

### 11.1 .NET — dotnet-trace (CPU + GC)

```bash
# Start steady-state benchmark in one terminal, then in another:
DURATION=30 bash benchmarks/profiling/dotnet-trace.sh
```

Output: `benchmarks/results/dotnet-trace-<timestamp>.speedscope.json`

Open at https://www.speedscope.app — drag and drop the `.speedscope.json` file.

**What to look for:** hot paths in `PlaceOrderHandler.Handle`, MediatR pipeline overhead, Kafka produce time.

Live metrics while running:
```bash
dotnet-counters monitor \
  --name OrderService.Api \
  System.Runtime Microsoft.AspNetCore.Hosting
```

### 11.2 Go — pprof CPU flamegraph

```bash
# Start steady-state benchmark in one terminal, then:
DURATION=30 bash benchmarks/profiling/pprof-cpu.sh
```

Output: `benchmarks/results/go-cpu-<timestamp>.pprof` + `.svg`

Interactive UI:
```bash
go tool pprof -http=:8090 benchmarks/results/go-cpu-<timestamp>.pprof
```
Open http://localhost:8090 → **Flame Graph** tab.

**What to look for:** goroutine scheduling in `dispatcher.go`, kafka-go write paths, JSON marshal overhead.

### 11.3 Go — heap + goroutines

```bash
bash benchmarks/profiling/pprof-mem.sh
```

Output: heap profile, heap flamegraph SVG, goroutine dump.

```bash
go tool pprof -http=:8090 benchmarks/results/go-heap-<timestamp>.pprof
```

---

## 12. Full Automated Run

Complete reproducibility sequence used to generate dissertation results:

```bash
# 1. Start the full stack (infrastructure + both services)
cd infrastructure
make up
# Wait ~45 seconds for Kafka to become healthy
make verify-env

# 2. Run all benchmarks (~35 min)
cd ..
./benchmarks/run-all.sh

# 3. Export data and run analysis (~5 min)
#    Must run while Prometheus is still up (within 7-day retention)
cd analysis
source .venv/bin/activate          # Windows: .venv\Scripts\activate
./run-analysis.sh

# 4. View results
open analysis/output/report/02-latency-analysis.html   # Mac
# Windows: start analysis\output\report\02-latency-analysis.html
open http://localhost:3000
```

**Total time from clone to results: approximately 45 minutes.**

Results are in:
- `benchmarks/results/` — k6 JSON summaries
- `analysis/output/figures/` — 8 publication-quality figures
- `analysis/output/tables/` — 5 Markdown + 5 LaTeX tables
- `analysis/output/report/` — 6 HTML notebook reports

---

## 13. Resetting the Environment

### 13.1 Soft reset (keep volumes and data)

```bash
cd infrastructure
make restart
```

Restarts all containers without removing volumes. Use this to apply config changes.

### 13.2 Hard reset (wipe everything)

```bash
cd infrastructure
make clean                                  # stops containers, removes volumes

# Clear benchmark and analysis output
rm -rf benchmarks/results/*.json
rm -rf benchmarks/results/*.pprof benchmarks/results/*.svg
rm -rf benchmarks/results/*.nettrace benchmarks/results/*.txt
rm -rf analysis/data/*.csv
rm -rf analysis/output/figures/* analysis/output/tables/* analysis/output/report/*
```

### 13.3 Start fresh after a hard reset

```bash
cd infrastructure
make up
# Wait ~45 seconds
make verify-env
```

---

## 14. CI/CD — GitHub Actions

### 14.1 Workflow file

The workflow is at [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

It runs on every push and pull request to `main`:
- **test-dotnet** — restore, build, test the .NET service
- **test-go** — build, vet, test (with `-race`) the Go service
- **test-analysis** — install Python deps and run `pytest`
- **docker-build** — build both Docker images (runs only if tests pass)

### 14.2 Status badge

Add to the root `README.md`:

```markdown
![CI](https://github.com/YOUR_USERNAME/eda-benchmark/actions/workflows/ci.yml/badge.svg)
```

### 14.3 Running CI checks locally

```bash
# .NET
cd services/dotnet && dotnet test -c Release

# Go
cd services/go && go test ./... -race

# Analysis
cd analysis && pytest tests/ -v
```
