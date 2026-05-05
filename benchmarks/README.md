# Benchmarks

Load tests, fault-injection scenarios, profiling scripts, and developer-experience
measurements for the `.NET + MediatR` vs `Go goroutines` EDA comparison.

## Prerequisites

| Tool | Minimum version | Purpose |
|------|----------------|---------|
| k6 | 0.49 | Load testing |
| Docker | 24 | Container management |
| Go toolchain | 1.22 | `go tool pprof` for flamegraphs |
| dotnet-trace | 8.x | .NET CPU / GC tracing (installed inside container) |

Start the full stack before running any benchmark:

```bash
cd infrastructure
docker compose up -d
```

## Directory layout

```
benchmarks/
├── steady-state/       k6 ramp-up → sustain → ramp-down (100 VU peak)
├── spike/              k6 sudden traffic burst (200 VU peak)
├── fault/
│   ├── network-delay   Services pre-configured with FAULT_DELAY_MS
│   ├── consumer-restart  Restart containers mid-run externally
│   └── broker-outage   Stop/start kafka mid-run externally
├── profiling/
│   ├── dotnet-trace.sh  CPU + GC via dotnet-trace → speedscope
│   ├── pprof-cpu.sh     Go CPU flamegraph
│   └── pprof-mem.sh     Go heap + goroutine dump
├── devex/
│   └── measure.sh      LoC, build times, test times, image sizes
├── results/            JSON summaries + profile files (git-ignored except .gitkeep)
└── run-all.sh          Run every k6 script in sequence
```

## Running benchmarks

### Full suite

```bash
cd benchmarks
bash run-all.sh
```

Override service URLs if not using defaults:

```bash
DOTNET_URL=http://localhost:8080 \
GO_URL=http://localhost:8081 \
PROM_RW_URL=http://localhost:9090/api/v1/write \
bash run-all.sh
```

### Individual k6 scripts

```bash
k6 run steady-state/steady-state.js
k6 run spike/spike.js
k6 run fault/network-delay.js
k6 run fault/consumer-restart.js
k6 run fault/broker-outage.js
```

With Prometheus remote-write output:

```bash
k6 run --out experimental-prometheus-rw=http://localhost:9090/api/v1/write \
  steady-state/steady-state.js
```

### Fault scenarios

#### Network delay

Set `FAULT_DELAY_MS` before starting the stack, then run:

```bash
FAULT_DELAY_MS=200 docker compose up -d go-service dotnet-service
k6 run fault/network-delay.js
```

Or inject at runtime via `docker compose restart` with updated env.

#### Consumer restart

While the k6 script is running (steady load at 30 VU), restart services in a separate terminal:

```bash
docker compose restart dotnet-service go-service
```

The script records 503 / connection-refused errors and measures how quickly the error
rate returns to baseline.

#### Broker outage

While the k6 script is running, stop and restart Kafka:

```bash
docker compose stop kafka
sleep 60
docker compose start kafka
```

Monitor Grafana → **EDA Overview** dashboard for consumer-group lag recovery.

## Profiling

All scripts write output to `results/` with a `YYYYMMDD-HHMMSS` timestamp suffix.

### .NET CPU + GC trace

```bash
bash profiling/dotnet-trace.sh            # default 30 s
DURATION=60 bash profiling/dotnet-trace.sh
```

Open the `.speedscope.json` file at <https://www.speedscope.app>.

### Go CPU flamegraph

```bash
bash profiling/pprof-cpu.sh               # default 30 s
DURATION=60 bash profiling/pprof-cpu.sh
```

### Go heap + goroutines

```bash
bash profiling/pprof-mem.sh
```

Interactive heap explorer:

```bash
go tool pprof -http=:6060 results/go-heap-<timestamp>.pprof
```

## Developer-experience metrics

```bash
bash devex/measure.sh
```

Captures: source LoC, file counts, build times, test execution times, dependency
counts, Docker image sizes. Report saved to `results/devex-<timestamp>.txt`.

## Makefile shortcuts

From `infrastructure/`:

```bash
make bench-steady
make bench-spike
make bench-fault-delay
make bench-fault-restart
make bench-fault-outage
make bench-all
make profile-dotnet
make profile-go-cpu
make profile-go-mem
make devex
```

## Results

After running, `results/` contains:

| File pattern | Contents |
|---|---|
| `steady-state-summary.json` | Full k6 data object for steady-state run |
| `spike-summary.json` | Full k6 data object for spike run |
| `network-delay-summary.json` | Full k6 data object for delay fault |
| `consumer-restart-summary.json` | Full k6 data object for restart fault |
| `broker-outage-summary.json` | Full k6 data object for outage fault |
| `dotnet-trace-*.nettrace` | Raw .NET trace (open in PerfView or VS) |
| `dotnet-trace-*.speedscope.json` | Flamegraph for speedscope.app |
| `go-cpu-*.pprof` | Go CPU profile |
| `go-cpu-*.svg` | Go CPU flamegraph SVG |
| `go-heap-*.pprof` | Go heap profile |
| `go-heap-*.svg` | Go heap flamegraph SVG |
| `go-goroutines-*.txt` | Goroutine dump |
| `devex-*.txt` | Developer experience report |

Grafana dashboards (http://localhost:3000, password: `benchmark`) provide real-time
views of all Prometheus metrics during k6 runs.
