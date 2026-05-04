# EDA Benchmark: Mediator + Kafka (.NET) vs Kafka (Go)

University dissertation project experimentally comparing two event-driven
architecture stacks across latency (P95/P99), throughput, CPU/memory, and
fault recovery.

| Stack | Components |
|-------|-----------|
| **.NET** | ASP.NET Core · MediatR · Confluent Kafka client |
| **Go** | Goroutines/channels · kafka-go |

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker Desktop | ≥ 25.0 | Run all infrastructure services |
| Docker Compose | ≥ 2.24 (bundled) | Orchestrate containers |
| k6 | ≥ 0.50 | Load testing |
| .NET SDK | 8.0 | Build the .NET service (P2) |
| Go | 1.22 | Build the Go service (P3) |

---

## Quick Start

```bash
# 1. Bring up Kafka, Prometheus, Grafana
make -f infrastructure/Makefile up

# 2. Wait ~30s for Kafka to be ready, then verify
make -f infrastructure/Makefile verify-env

# 3. Open Grafana
#    URL:  http://localhost:3000
#    User: admin   Password: benchmark
```

> The .NET service (P2) and Go service (P3) are **not started yet**.
> Placeholder blocks are in `infrastructure/docker-compose.yml` — uncomment
> them after completing the respective phase.

---

## Project Structure

```
eda-benchmark/
├── .gitignore
├── README.md
├── infrastructure/
│   ├── Makefile                        # all operational targets
│   ├── docker-compose.yml              # Kafka, Prometheus, Grafana (+placeholders)
│   ├── monitoring/
│   │   ├── prometheus.yml              # scrape config (jobs for P2/P3 commented out)
│   │   └── provisioning/
│   │       ├── datasources/
│   │       │   └── prometheus.yml      # Grafana datasource auto-provisioning
│   │       └── dashboards/
│   │           ├── dashboards.yml      # Grafana dashboard provider config
│   │           └── overview.json       # "EDA Benchmark Overview" dashboard
│   └── k6/
│       └── baseline.js                 # load test (baseline + spike scenarios)
├── services/
│   ├── dotnet/                         # ASP.NET Core + MediatR service (P2)
│   └── go/                             # Go service (P3)
├── benchmarks/                         # benchmark run scripts / config
├── analysis/                           # Jupyter notebooks, R scripts, charts
├── docs/                               # dissertation supporting material
└── results/                            # k6 JSON output (git-ignored)
```

---

## Ports

| Service | Host Port | URL |
|---------|-----------|-----|
| Kafka (external) | 9092 | `localhost:9092` |
| Kafka JMX | 9101 | — |
| Kafka Exporter | 9308 | `http://localhost:9308/metrics` |
| Prometheus | 9090 | `http://localhost:9090` |
| Grafana | 3000 | `http://localhost:3000` |
| .NET service (P2) | 8080 | `http://localhost:8080` |
| Go service (P3) | 8081 | `http://localhost:8081` |

---

## Kafka Topics

| Topic | Partitions | Replication | Purpose |
|-------|-----------|-------------|---------|
| `orders.placed` | 3 | 1 | Inbound order events from the API |
| `orders.processed` | 3 | 1 | Successfully handled orders |
| `orders.failed` | 1 | 1 | Dead-letter / error events |

---

## Running Benchmarks

```bash
# Baseline scenario  (0→10→50→100→50→0 VUs, ~4.5 min)
make -f infrastructure/Makefile k6-baseline

# Spike scenario  (0→50→200→0 VUs, ~1 min)
make -f infrastructure/Makefile k6-spike

# Override service URLs
make -f infrastructure/Makefile k6-baseline \
  DOTNET_URL=http://localhost:8080 \
  GO_URL=http://localhost:8081

# Results land in results/<scenario>-summary.json
# Live metrics stream to Grafana via Prometheus remote-write
```

k6 pushes metrics to Prometheus remote-write at `http://localhost:9090/api/v1/write`.
The **EDA Benchmark Overview** dashboard in Grafana auto-refreshes every 10 s.

---

## Adding a Service (P2 / P3)

1. Implement the service in `services/dotnet/` or `services/go/`.
2. Expose `GET /health` and `POST /orders` on the configured port.
3. Expose Prometheus metrics on `/metrics` (port 8080 or 8081).
4. Uncomment the relevant service block in `infrastructure/docker-compose.yml`.
5. Uncomment the matching scrape job in `infrastructure/monitoring/prometheus.yml`.
6. Run `make -f infrastructure/Makefile restart` and `verify-env`.

---

## Makefile Targets

| Target | Description |
|--------|-------------|
| `up` | Start all infrastructure containers |
| `down` | Stop containers (keeps volumes) |
| `restart` | Restart all containers |
| `logs` | Follow container logs |
| `kafka-topics` | List topics inside the broker |
| `verify-env` | Health-check all services |
| `k6-baseline` | Run the baseline load test |
| `k6-spike` | Run the spike load test |
| `clean` | Destroy containers **and volumes** + wipe results/ |
