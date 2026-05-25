| Metric             | .NET mean   | Go mean    | Diff       | 95% CI           | p-value   | Effect     | Winner   |
|:-------------------|:------------|:-----------|:-----------|:-----------------|:----------|:-----------|:---------|
| P95 Latency        | 71.06 ms    | 68.00 ms   | +3.07 ms   | [-9.03, +15.10]  | <0.0001   | small      | GO       |
| P99 Latency        | 92.51 ms    | 76.74 ms   | +15.76 ms  | [+3.40, +28.19]  | 0.0007    | negligible | GO       |
| Throughput         | 341.27 rps  | 284.80 rps | +56.47 rps | [+17.52, +97.26] | 0.0690    | negligible | TIE      |
| CPU Usage          | 52.31 %     | 25.22 %    | +27.10 %   | [+23.64, +30.62] | <0.0001   | large      | GO       |
| Heap Memory        | 22.32 MB    | 6.31 MB    | +16.01 MB  | [+14.73, +17.33] | <0.0001   | large      | GO       |
| Error Rate (Fault) | nan rate    | nan rate   | +nan rate  | [+nan, +nan]     | <0.0001   | n/a        | N/A      |