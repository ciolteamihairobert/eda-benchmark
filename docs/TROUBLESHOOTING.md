# EDA Benchmark — Troubleshooting Guide

Entries are organised by the exact error message or symptom you see in your terminal.  
For setup context, see [RUNNING.md](RUNNING.md).

---

### ❌ Kafka not starting / "broker may not be available"

**Cause:** Port 9092 is already in use by another Kafka instance, or Zookeeper has not yet passed its healthcheck when Kafka tries to connect.

**Fix:**
```bash
# Check what is using the port
lsof -i :9092

# Kill the conflicting process (replace <PID>)
kill <PID>

# Or on Windows PowerShell:
netstat -ano | findstr :9092
Stop-Process -Id <PID>

# Restart the stack cleanly
cd infrastructure
make down
make up
```

**Verify:**
```bash
make kafka-topics
# Expected: orders.failed  orders.placed  orders.processed
```

---

### ❌ Kafka topics not created

**Cause:** The `kafka-init` one-shot container exited before Kafka was fully ready to accept connections, so the topic creation commands were never sent.

**Fix:**
```bash
# Check what kafka-init logged
docker compose -f infrastructure/docker-compose.yml logs kafka-init

# Re-run it manually
docker compose -f infrastructure/docker-compose.yml up kafka-init
```

**Verify:**
```bash
make kafka-topics
# Expected: three topics listed
```

---

### ❌ .NET service crashes on startup — "No such host 'kafka'"

**Cause:** When running locally with `dotnet run`, `Kafka__BootstrapServers` still points to `kafka` (the Docker hostname), which is only resolvable inside the Docker network.

**Fix (local run):**
```bash
# Mac/Linux
Kafka__BootstrapServers=localhost:9092 dotnet run \
  --project src/OrderService.Api --configuration Release

# Windows PowerShell
$env:Kafka__BootstrapServers = "localhost:9092"
dotnet run --project src\OrderService.Api --configuration Release
```

**Fix (Docker):** Ensure `depends_on` in `docker-compose.yml` includes `kafka: condition: service_healthy`. This is already configured — if the error persists, Kafka is not yet healthy; wait and retry `make up`.

**Verify:**
```bash
curl http://localhost:8080/health
# Expected: {"status":"ok","timestamp":"..."}
```

---

### ❌ Go service — "dial tcp: lookup kafka: no such host"

**Cause:** Same as above — running locally with `KAFKA_BOOTSTRAP=kafka:29092` (the Docker-internal address).

**Fix (local run):**
```bash
KAFKA_BOOTSTRAP=localhost:9092 go run ./cmd/server
```

**Fix (Docker):** `KAFKA_BOOTSTRAP: kafka:29092` is set correctly in `docker-compose.yml`. If the error appears in container logs, Kafka started before `kafka-init` finished. Run `make down && make up`.

**Verify:**
```bash
curl http://localhost:8081/health
# Expected: {"status":"ok","timestamp":"..."}
```

---

### ❌ Prometheus shows `dotnet-service` or `go-service` as DOWN

**Cause:** The service is not running, is on the wrong port, or the scrape target in `prometheus.yml` is incorrect.

**Fix:**
```bash
# 1. Confirm the service is up
curl http://localhost:8080/metrics    # .NET
curl http://localhost:8081/metrics    # Go

# 2. Check prometheus.yml has the correct targets
cat infrastructure/monitoring/prometheus.yml

# 3. Reload Prometheus config (no restart needed)
curl -X POST http://localhost:9090/-/reload

# 4. Check container logs for scrape errors
docker compose -f infrastructure/docker-compose.yml logs prometheus --tail=30
```

**Verify:**  
Open http://localhost:9090/targets — both services should show **State = UP**.

---

### ❌ Grafana shows "No data" on all panels

**Cause:** The Prometheus datasource URL is wrong, or Prometheus is not running.

**Fix:**
```bash
# Confirm Prometheus is healthy
curl http://localhost:9090/-/healthy
# Expected: Prometheus Server is Healthy.

# In Grafana: Configuration → Data Sources → Prometheus → Test
# If it fails, check the URL is: http://prometheus:9090 (not localhost:9090)
# inside the Docker network, Grafana reaches Prometheus via the service name.
```

**Verify:**  
Grafana → Explore → run query `up` — should return results.

---

### ❌ k6 error: `experimental-prometheus-rw output not available`

**Cause:** k6 version is older than 0.46.0, which introduced the experimental Prometheus remote-write output.

**Fix:**
```bash
k6 version
# Should be ≥ 0.50.0

# Upgrade
brew upgrade k6          # Mac
choco upgrade k6         # Windows
```

**Verify:**
```bash
k6 run --out experimental-prometheus-rw=http://localhost:9090/api/v1/write \
  benchmarks/steady-state/steady-state.js
```

---

### ❌ k6 error: `ECONNREFUSED localhost:8080` or `localhost:8081`

**Cause:** One or both services are not running when k6 tries to send requests.

**Fix:**
```bash
cd infrastructure
make verify-env
# Identify which service is not reachable, then start it (Sections 4 or 5 of RUNNING.md)
```

**Verify:**
```bash
curl http://localhost:8080/health && curl http://localhost:8081/health
```

---

### ❌ `dotnet-trace`: "No compatible .NET runtime found in container"

**Cause:** The `dotnet-trace` global tool is not installed inside the container. The distroless production image does not include .NET global tools by default.

**Fix:**  
The provided `benchmarks/profiling/dotnet-trace.sh` script uses the container's process PID and assumes `dotnet-trace` is available at the system level on the host for Docker exec. Install it on the host:

```bash
dotnet tool install -g dotnet-trace
export PATH="$PATH:$HOME/.dotnet/tools"
dotnet-trace --version
```

Then re-run:
```bash
bash benchmarks/profiling/dotnet-trace.sh
```

**Verify:**
```bash
ls benchmarks/results/dotnet-trace-*.nettrace
```

---

### ❌ pprof: `curl: (7) Failed to connect to localhost port 8081`

**Cause:** The Go service is not running, or pprof is not being registered. The service registers pprof routes at `/debug/pprof/*` only when running — it is not available during container startup.

**Fix:**
```bash
# Confirm Go service is running
curl http://localhost:8081/health

# Confirm pprof endpoint is reachable
curl http://localhost:8081/debug/pprof/
# Expected: HTML page listing profile types
```

**Verify:**
```bash
curl -s http://localhost:8081/debug/pprof/goroutine?debug=1 | head -5
```

---

### ❌ Python: `ModuleNotFoundError: No module named 'pandas'`

**Cause:** The virtual environment is not activated, or `requirements.txt` has not been installed.

**Fix:**
```bash
cd analysis

# Create and activate venv if not done yet
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify
python3 -c "import pandas; print(pandas.__version__)"
```

**Verify:**
```bash
python3 -c "import pandas, scipy, matplotlib, pingouin; print('All OK')"
```

---

### ❌ `export_prometheus.py` — "No data returned for query"

**Cause:** Prometheus retention has been exceeded (default 7 days), the wrong time range was specified, or Prometheus is not running.

**Fix:**
```bash
# Check Prometheus is reachable
curl http://localhost:9090/api/v1/query?query=up

# Check what data is available
curl "http://localhost:9090/api/v1/query_range?query=up&start=$(date -d '2 hours ago' +%s)&end=$(date +%s)&step=60"

# If data exists, specify the exact benchmark window
python3 scripts/export_prometheus.py \
  --start 2024-01-15T10:00:00Z \
  --end   2024-01-15T12:00:00Z
```

**Verify:**
```bash
ls -la analysis/data/*.csv | head -10
```

---

### ❌ `analysis/data/` is empty after export

**Cause:** Prometheus URL is wrong, Prometheus container is not running, or k6 remote-write did not reach Prometheus during the benchmark.

**Fix:**
```bash
# Test Prometheus URL directly
curl http://localhost:9090/api/v1/query?query=up

# Run export with explicit URL
PROMETHEUS_URL=http://localhost:9090 python3 scripts/export_prometheus.py

# Check if k6 metrics exist in Prometheus
curl "http://localhost:9090/api/v1/label/__name__/values" | python3 -m json.tool | grep k6
```

If no `k6_*` metrics appear, the benchmark must be re-run with `--out experimental-prometheus-rw` — see Section 7 of [RUNNING.md](RUNNING.md).

**Verify:**
```bash
ls analysis/data/ | wc -l
# Expected: 20 or more CSV files
```

---

### ❌ Docker: `ERROR: Bind for 0.0.0.0:9092 failed: port is already allocated`

**Cause:** A previous Docker stack was not fully stopped, or another process is listening on the port.

**Fix:**
```bash
# Stop any running compose stacks
cd infrastructure && make down

# Find the container still holding the port
docker ps -a | grep kafka
docker rm -f <container_id>

# Or find the host process
lsof -i :9092
kill <PID>
```

**Verify:**
```bash
make up
docker compose -f infrastructure/docker-compose.yml ps
```

---

### ❌ Docker: out of disk space

**Cause:** Accumulated images and anonymous volumes from repeated `make up` / `make down` cycles.

**Fix:**
```bash
# Safe cleanup (removes stopped containers, dangling images, unused networks)
docker system prune -f

# Also remove unused volumes (WARNING: deletes Prometheus and Grafana data)
docker volume prune -f

# Nuclear option (removes everything including named volumes and all images)
docker system prune -a --volumes -f
```

**Verify:**
```bash
docker system df
# "Total reclaimable" should be reduced
```

---

### ❌ `make verify-env` shows all ✗ immediately after `make up`

**Cause:** Kafka takes 30–45 seconds to become healthy. `make verify-env` run too soon will report all services as unreachable.

**Fix:**
```bash
# Check if containers are still starting
docker compose -f infrastructure/docker-compose.yml ps
# Look for "starting" or "unhealthy" status — wait until all show "healthy"

# Then retry
make verify-env
```

**Verify:**  
All five lines show `OK`.

---

### ❌ Consumer lag grows indefinitely during a load test

**Cause:** The consumer is processing messages slower than they are produced. Possible causes: too few workers (`WORKER_COUNT` too low for Go), thread-pool saturation (.NET), or fault injection left active.

**Fix:**
```bash
# Check service logs for processing errors
docker compose -f infrastructure/docker-compose.yml logs go-service --tail=50
docker compose -f infrastructure/docker-compose.yml logs dotnet-service --tail=50

# Verify fault injection is off (FAULT_DELAY_MS and FAULT_FAIL_RATE should be 0)
docker inspect go-service | grep -A2 FAULT

# Check consumer group membership and lag
docker compose -f infrastructure/docker-compose.yml exec kafka \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group go-order-service

docker compose -f infrastructure/docker-compose.yml exec kafka \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group dotnet-order-service
```

**Verify:**  
Grafana **Kafka Consumer Lag** panel returns to near 0 after the load test ends.

---

### ❌ Statistical tests fail — "not enough data points" or all results empty

**Cause:** The benchmark ran too briefly, the export time range was too narrow, or the CSVs are empty.

**Fix:**
```bash
# Check how many rows are in the latency CSVs
wc -l analysis/data/latency_p95_dotnet.csv analysis/data/latency_p95_go.csv
# Anything below ~60 rows (10 min at 10s step) is too sparse

# Re-run the steady-state benchmark with full duration
cd infrastructure && make bench-steady

# Re-export with the correct window
python3 analysis/scripts/export_prometheus.py \
  --start <benchmark_start_ISO> \
  --end   <benchmark_end_ISO>
```

**Verify:**
```bash
python3 analysis/scripts/statistical_tests.py
# Should print a populated results table
```
