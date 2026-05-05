##############################################################################
# EDA Benchmark — infrastructure Makefile
# Run from the repo root:  make -f infrastructure/Makefile <target>
# Or cd infrastructure && make <target>
##############################################################################

COMPOSE_FILE := infrastructure/docker-compose.yml
BENCH_DIR    := benchmarks
# Allow overrides:  make k6-baseline DOTNET_URL=http://...
DOTNET_URL   ?= http://localhost:8080
GO_URL       ?= http://localhost:8081
PROM_RW_URL  ?= http://localhost:9090/api/v1/write

K6_OPTS      := --out experimental-prometheus-rw=$(PROM_RW_URL) \
                -e DOTNET_URL=$(DOTNET_URL) \
                -e GO_URL=$(GO_URL) \
                -e PROM_RW_URL=$(PROM_RW_URL)

PROFILE_ENV  := GO_URL=$(GO_URL)

.PHONY: up down restart logs kafka-topics verify-env \
        k6-baseline k6-spike \
        bench-steady bench-spike bench-fault-delay bench-fault-restart bench-fault-outage bench-all \
        profile-dotnet profile-go-cpu profile-go-mem devex \
        clean

## ── Docker Compose ──────────────────────────────────────────────────────────

up:
	docker compose -f $(COMPOSE_FILE) up -d --build
	@echo ""
	@echo "Infrastructure is starting. Run 'make verify-env' in ~30s to check readiness."

down:
	docker compose -f $(COMPOSE_FILE) down

restart:
	docker compose -f $(COMPOSE_FILE) restart

logs:
	docker compose -f $(COMPOSE_FILE) logs -f

## ── Kafka ───────────────────────────────────────────────────────────────────

kafka-topics:
	docker compose -f $(COMPOSE_FILE) exec kafka \
		kafka-topics --bootstrap-server kafka:29092 --list

## ── Environment verification ────────────────────────────────────────────────

verify-env:
	@echo "=========================================="
	@echo " EDA Benchmark — service health check"
	@echo "=========================================="
	@printf "Kafka:          "; \
		docker compose -f $(COMPOSE_FILE) exec -T kafka \
			kafka-broker-api-versions --bootstrap-server localhost:9092 \
			> /dev/null 2>&1 \
			&& echo "OK" || echo "UNREACHABLE"
	@printf "Prometheus:     "; \
		curl -sf http://localhost:9090/-/healthy > /dev/null \
			&& echo "OK  →  http://localhost:9090" \
			|| echo "UNREACHABLE"
	@printf "Grafana:        "; \
		curl -sf http://localhost:3000/api/health > /dev/null \
			&& echo "OK  →  http://localhost:3000  (admin / benchmark)" \
			|| echo "UNREACHABLE"
	@printf "dotnet-service: "; \
		curl -sf $(DOTNET_URL)/health > /dev/null \
			&& echo "OK  →  $(DOTNET_URL)" \
			|| echo "not reachable — start P2 first"
	@printf "go-service:     "; \
		curl -sf $(GO_URL)/health > /dev/null \
			&& echo "OK  →  $(GO_URL)" \
			|| echo "not reachable — start P3 first"
	@echo "=========================================="

## ── k6 load tests ───────────────────────────────────────────────────────────

k6-baseline:
	mkdir -p results
	K6_PROMETHEUS_RW_SERVER_URL=$(PROM_RW_URL) \
		k6 run $(K6_OPTS) \
		-e SCENARIO=baseline \
		infrastructure/k6/baseline.js

k6-spike:
	mkdir -p results
	K6_PROMETHEUS_RW_SERVER_URL=$(PROM_RW_URL) \
		k6 run $(K6_OPTS) \
		-e SCENARIO=spike \
		infrastructure/k6/baseline.js

## ── P4 benchmark suite ──────────────────────────────────────────────────────

bench-steady:
	k6 run $(K6_OPTS) $(BENCH_DIR)/steady-state/steady-state.js

bench-spike:
	k6 run $(K6_OPTS) $(BENCH_DIR)/spike/spike.js

bench-fault-delay:
	k6 run $(K6_OPTS) $(BENCH_DIR)/fault/network-delay.js

bench-fault-restart:
	k6 run $(K6_OPTS) $(BENCH_DIR)/fault/consumer-restart.js

bench-fault-outage:
	k6 run $(K6_OPTS) $(BENCH_DIR)/fault/broker-outage.js

bench-all:
	bash $(BENCH_DIR)/run-all.sh

## ── Profiling ───────────────────────────────────────────────────────────────

profile-dotnet:
	bash $(BENCH_DIR)/profiling/dotnet-trace.sh

profile-go-cpu:
	$(PROFILE_ENV) bash $(BENCH_DIR)/profiling/pprof-cpu.sh

profile-go-mem:
	$(PROFILE_ENV) bash $(BENCH_DIR)/profiling/pprof-mem.sh

## ── Developer experience ────────────────────────────────────────────────────

devex:
	bash $(BENCH_DIR)/devex/measure.sh

## ── Cleanup ─────────────────────────────────────────────────────────────────

clean:
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans
	rm -rf results/ $(BENCH_DIR)/results/*.json $(BENCH_DIR)/results/*.pprof \
	       $(BENCH_DIR)/results/*.svg $(BENCH_DIR)/results/*.nettrace \
	       $(BENCH_DIR)/results/*.txt
	@echo "Volumes removed and results cleared."
