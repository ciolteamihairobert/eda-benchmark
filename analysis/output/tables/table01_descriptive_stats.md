| Metric (Service)                         |    Mean |     Std |   Min |   P50 |     P95 |      P99 |      Max | Unit   |
|:-----------------------------------------|--------:|--------:|------:|------:|--------:|---------:|---------:|:-------|
| P95 Latency (.NET (MediatR + Kafka))     |  960.17 | 3312.02 |  7.8  | 12.74 | 7987.2  | 14708.7  | 15564.8  | ms     |
| P95 Latency (Go (goroutines + kafka-go)) |   24.29 |    0.19 | 24.11 | 24.22 |   24.78 |    24.92 |    25.15 | ms     |
| P99 Latency (.NET (MediatR + Kafka))     | 1048.78 | 3613.84 |  7.96 | 15.69 | 8151.04 | 16049    | 16220.2  | ms     |
| P99 Latency (Go (goroutines + kafka-go)) |   27.75 |    8.37 | 24.82 | 24.85 |   44.19 |    46.52 |    88.8  | ms     |
| Throughput (.NET (MediatR + Kafka))      |  158.53 |  274.53 |  0    | 14.83 |  722.4  |  1286.12 |  1382.02 | rps    |
| Throughput (Go (goroutines + kafka-go))  |  135.09 |  207.7  |  0    |  9.36 |  648.55 |   724.67 |   749.17 | rps    |
| CPU Usage (.NET (MediatR + Kafka))       |   27.45 |   24.51 |  0.38 | 20.33 |   82.09 |   122.47 |   126.47 | %      |
| CPU Usage (Go (goroutines + kafka-go))   |   13.77 |   12.15 |  0.04 | 10.96 |   42.09 |    59.2  |    60.86 | %      |
| Heap Memory (.NET (MediatR + Kafka))     |   17.65 |    9.59 |  2.9  | 16.77 |   33.24 |    35    |    47    | MB     |
| Heap Memory (Go (goroutines + kafka-go)) |    5.81 |    1.33 |  3.64 |  5.49 |    8.37 |    10.12 |    10.41 | MB     |