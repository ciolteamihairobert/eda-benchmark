| Metric             | .NET mean   | Go mean    | Diff        | 95% CI              | p-value   | Effect   | Winner   |
|:-------------------|:------------|:-----------|:------------|:--------------------|:----------|:---------|:---------|
| P95 Latency        | 960.17 ms   | 24.29 ms   | +935.88 ms  | [+362.55, +1597.56] | <0.0001   | small    | GO       |
| P99 Latency        | 1048.78 ms  | 27.75 ms   | +1021.03 ms | [+430.32, +1747.90] | 0.0002    | medium   | GO       |
| Throughput         | 158.53 rps  | 135.09 rps | +23.44 rps  | [-23.44, +71.59]    | 0.8411    | large    | TIE      |
| CPU Usage          | 27.45 %     | 13.77 %    | +13.68 %    | [+10.01, +17.60]    | <0.0001   | large    | GO       |
| Heap Memory        | 17.65 MB    | 5.81 MB    | +11.84 MB   | [+10.50, +13.22]    | <0.0001   | large    | GO       |
| Error Rate (Fault) | nan rate    | nan rate   | +nan rate   | [+nan, +nan]        | <0.0001   | n/a      | N/A      |