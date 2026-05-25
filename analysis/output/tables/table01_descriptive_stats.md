| Metric (Service)                         |   Mean |    Std |   Min |    P50 |    P95 |     P99 |     Max | Unit   |
|:-----------------------------------------|-------:|-------:|------:|-------:|-------:|--------:|--------:|:-------|
| P95 Latency (.NET (MediatR + Kafka))     |  71.06 |  91.03 |  7.91 |  21.41 | 249.72 |  250.6  |  251.14 | ms     |
| P95 Latency (Go (goroutines + kafka-go)) |  68    |  85.45 | 24.12 |  24.34 | 242.5  |  243.48 |  243.94 | ms     |
| P99 Latency (.NET (MediatR + Kafka))     |  92.51 |  93.48 | 13.44 |  43.2  | 254.97 |  255.89 |  441.7  | ms     |
| P99 Latency (Go (goroutines + kafka-go)) |  76.74 |  88.93 | 24.83 |  25.53 | 248.5  |  249.57 |  480.5  | ms     |
| Throughput (.NET (MediatR + Kafka))      | 341.27 | 346.47 |  0    | 239.48 | 989.97 | 1335.37 | 1385.98 | rps    |
| Throughput (Go (goroutines + kafka-go))  | 284.8  | 264.77 |  0    | 213.92 | 730.89 |  771.68 |  776.6  | rps    |
| CPU Usage (.NET (MediatR + Kafka))       |  52.31 |  33.74 |  0.28 |  42.37 | 122.23 |  136.61 |  139.87 | %      |
| CPU Usage (Go (goroutines + kafka-go))   |  25.22 |  16.76 |  0.08 |  21.33 |  57.59 |   63.92 |   64.76 | %      |
| Heap Memory (.NET (MediatR + Kafka))     |  22.32 |  13.88 |  2.18 |  20.79 |  49.9  |   69.95 |   79.62 | MB     |
| Heap Memory (Go (goroutines + kafka-go)) |   6.31 |   1.65 |  3.45 |   6.12 |   9.47 |   10.21 |   10.44 | MB     |