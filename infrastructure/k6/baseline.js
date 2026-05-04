/**
 * EDA Benchmark — k6 load test
 *
 * Scenarios:
 *   baseline  – ramp 0→10→50→100→50→0 VUs over ~4.5 min
 *   spike     – short ramp to 200 VUs then cut
 *
 * Override via env:  k6 run -e SCENARIO=spike baseline.js
 * Remote-write:      K6_PROMETHEUS_RW_SERVER_URL=http://localhost:9090/api/v1/write k6 run ...
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';

// ── Custom metrics ────────────────────────────────────────────────────────────
const dotnetDuration  = new Trend('dotnet_duration',   true);  // ms
const goDuration      = new Trend('go_duration',       true);  // ms
const dotnetErrors    = new Counter('dotnet_errors');
const goErrors        = new Counter('go_errors');
const dotnetErrorRate = new Rate('dotnet_error_rate');
const goErrorRate     = new Rate('go_error_rate');

// ── Config ────────────────────────────────────────────────────────────────────
const DOTNET_URL = __ENV.DOTNET_URL || 'http://localhost:8080';
const GO_URL     = __ENV.GO_URL     || 'http://localhost:8081';
const SCENARIO   = __ENV.SCENARIO   || 'baseline';

// ── Scenarios ─────────────────────────────────────────────────────────────────
const scenarios = {
  baseline: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '30s', target: 10  },   // warm-up
      { duration: '2m',  target: 50  },   // ramp
      { duration: '30s', target: 100 },   // peak
      { duration: '1m',  target: 50  },   // scale-down
      { duration: '30s', target: 0   },   // cool-down
    ],
    gracefulRampDown: '10s',
  },
  spike: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '15s', target: 50  },   // fast ramp
      { duration: '30s', target: 200 },   // spike plateau
      { duration: '15s', target: 0   },   // instant drop
    ],
    gracefulRampDown: '5s',
  },
};

export const options = {
  scenarios: {
    [SCENARIO]: scenarios[SCENARIO],
  },
  thresholds: {
    // P95 < 300 ms, P99 < 500 ms for both services
    dotnet_duration:   ['p(95)<300', 'p(99)<500'],
    go_duration:       ['p(95)<300', 'p(99)<500'],
    // Error rate < 1%
    dotnet_error_rate: ['rate<0.01'],
    go_error_rate:     ['rate<0.01'],
  },
};

// ── Payload factory ───────────────────────────────────────────────────────────
function generateOrder() {
  return JSON.stringify({
    orderId:    `ord-${__VU}-${__ITER}-${Date.now()}`,
    customerId: `cust-${Math.floor(Math.random() * 1000)}`,
    items: [
      {
        sku:      `SKU-${String(Math.floor(Math.random() * 100)).padStart(3, '0')}`,
        quantity: Math.floor(Math.random() * 5) + 1,
        price:    parseFloat((Math.random() * 99 + 1).toFixed(2)),
      },
    ],
    timestamp: new Date().toISOString(),
  });
}

// ── VU main loop ──────────────────────────────────────────────────────────────
export default function () {
  const payload = generateOrder();
  const headers = { 'Content-Type': 'application/json' };

  // Fire both requests in parallel within this VU iteration
  const responses = http.batch([
    {
      method: 'POST',
      url:    `${DOTNET_URL}/orders`,
      body:   payload,
      params: { headers, tags: { service: 'dotnet' } },
    },
    {
      method: 'POST',
      url:    `${GO_URL}/orders`,
      body:   payload,
      params: { headers, tags: { service: 'go' } },
    },
  ]);

  const [dotnetRes, goRes] = responses;

  // Record durations
  dotnetDuration.add(dotnetRes.timings.duration, { service: 'dotnet' });
  goDuration.add(goRes.timings.duration,         { service: 'go' });

  // Checks + error tracking
  const dotnetOK = check(dotnetRes, {
    'dotnet status 2xx': (r) => r.status >= 200 && r.status < 300,
  });
  const goOK = check(goRes, {
    'go status 2xx': (r) => r.status >= 200 && r.status < 300,
  });

  dotnetErrorRate.add(!dotnetOK);
  goErrorRate.add(!goOK);
  if (!dotnetOK) dotnetErrors.add(1);
  if (!goOK)     goErrors.add(1);

  sleep(Math.random() * 0.5 + 0.1); // 100–600 ms think time
}

// ── Summary ───────────────────────────────────────────────────────────────────
export function handleSummary(data) {
  const m = data.metrics;

  const fmt = (metric, pct) =>
    m[metric]?.values?.[`p(${pct})`]?.toFixed(2) ?? 'N/A';

  const report = [
    '',
    '╔══════════════════════════════════════════════╗',
    '║         EDA Benchmark — Run Summary          ║',
    '╠══════════════════════════════════════════════╣',
    `║  Scenario : ${(SCENARIO + ' '.repeat(32)).slice(0, 32)}║`,
    '╠══════════════════════════╦════════╦══════════╣',
    '║  Service                 ║  P95   ║  P99     ║',
    '╠══════════════════════════╬════════╬══════════╣',
    `║  .NET (dotnet_duration)  ║ ${(fmt('dotnet_duration','95') + 'ms      ').slice(0,6)} ║ ${(fmt('dotnet_duration','99') + 'ms        ').slice(0,8)} ║`,
    `║  Go   (go_duration)      ║ ${(fmt('go_duration','95')     + 'ms      ').slice(0,6)} ║ ${(fmt('go_duration','99')     + 'ms        ').slice(0,8)} ║`,
    '╠══════════════════════════╩════════╩══════════╣',
    `║  dotnet errors : ${String(m.dotnet_errors?.values?.count ?? 0).padEnd(27)}║`,
    `║  go errors     : ${String(m.go_errors?.values?.count ?? 0).padEnd(27)}║`,
    '╚══════════════════════════════════════════════╝',
    '',
  ].join('\n');

  const filename = `results/${SCENARIO}-summary.json`;

  return {
    [filename]: JSON.stringify(data, null, 2),
    stdout: report,
  };
}
