import http from "k6/http";
import { sleep } from "k6";
import { Trend, Counter, Rate } from "k6/metrics";
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.2/index.js";

const dotnetDuration    = new Trend("dotnet_duration",      true);
const goDuration        = new Trend("go_duration",          true);
const dotnetErrors      = new Counter("dotnet_errors");
const goErrors          = new Counter("go_errors");
const dotnetSuccessRate = new Rate("dotnet_success_rate");
const goSuccessRate     = new Rate("go_success_rate");

const DOTNET_URL  = __ENV.DOTNET_URL  || "http://localhost:8080";
const GO_URL      = __ENV.GO_URL      || "http://localhost:8081";

// Expected usage — run from a separate terminal while this script is active:
//   docker compose stop kafka          (trigger outage ~30 s in)
//   sleep 60 && docker compose start kafka   (restore)
// The script records error rates during the outage and recovery latency.
export const options = {
  scenarios: {
    broker_outage: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s",  target: 20 },
        { duration: "120s", target: 20 },
        { duration: "30s",  target: 0  },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    dotnet_success_rate: ["rate>0.80"],
    go_success_rate:     ["rate>0.80"],
  },
};

function makeOrder(vu, iter) {
  return JSON.stringify({
    orderId:    `ord-outage-${vu}-${iter}`,
    customerId: `cust-${vu}`,
    items: [{ sku: "SKU-005", quantity: 1, price: 29.99 }],
    timestamp: new Date().toISOString(),
  });
}

const headers = { "Content-Type": "application/json" };

export default function () {
  const body = makeOrder(__VU, __ITER);

  const dotnetRes = http.post(`${DOTNET_URL}/orders`, body, {
    headers,
    tags: { service: "dotnet" },
    timeout: "8s",
  });
  dotnetDuration.add(dotnetRes.timings.duration, { service: "dotnet" });
  const dotnetOk = dotnetRes.status === 202;
  dotnetSuccessRate.add(dotnetOk, { service: "dotnet" });
  if (!dotnetOk) dotnetErrors.add(1, { service: "dotnet" });

  const goRes = http.post(`${GO_URL}/orders`, body, {
    headers,
    tags: { service: "go" },
    timeout: "8s",
  });
  goDuration.add(goRes.timings.duration, { service: "go" });
  const goOk = goRes.status === 202;
  goSuccessRate.add(goOk, { service: "go" });
  if (!goOk) goErrors.add(1, { service: "go" });

  sleep(0.1);
}

export function handleSummary(data) {
  const dn = data.metrics.dotnet_duration?.values ?? {};
  const go = data.metrics.go_duration?.values ?? {};
  const dur = (data.state.testRunDurationMs ?? 0) / 1000;
  const total = data.metrics.http_reqs?.values?.count ?? 0;
  const rps = dur > 0 ? (total / dur).toFixed(1) : "n/a";

  const dnErrRate = data.metrics.dotnet_success_rate?.values?.rate ?? 1;
  const goErrRate = data.metrics.go_success_rate?.values?.rate ?? 1;

  const table = [
    "┌──────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐",
    "│ Service      │   P50 ms │   P95 ms │   P99 ms │      RPS │ Err rate │",
    "├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤",
    `│ .NET         │ ${fmt(dn["p(50)"])} │ ${fmt(dn["p(95)"])} │ ${fmt(dn["p(99)"])} │ ${rps.toString().padStart(8)} │ ${pct(1 - dnErrRate)} │`,
    `│ Go           │ ${fmt(go["p(50)"])} │ ${fmt(go["p(95)"])} │ ${fmt(go["p(99)"])} │ ${rps.toString().padStart(8)} │ ${pct(1 - goErrRate)} │`,
    "└──────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘",
  ].join("\n");

  console.log("\n=== Broker-Outage Fault Results ===\n" + table);

  return {
    "benchmarks/results/broker-outage-summary.json": JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: " ", enableColors: true }),
  };
}

function fmt(v) { return v == null ? "    n/a " : v.toFixed(1).padStart(8); }
function pct(v) { return v == null ? "    n/a " : (v * 100).toFixed(2).padStart(7) + "%"; }
