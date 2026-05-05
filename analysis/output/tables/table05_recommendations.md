| Scenario                          | Recommended Stack   | Rationale                                                           |
|:----------------------------------|:--------------------|:--------------------------------------------------------------------|
| High throughput (>10k msg/s)      | Go                  | Lower per-goroutine overhead; no MediatR dispatch allocations       |
| Low latency SLA (<50ms P99)       | Go                  | Minimal GC pause times; direct channel dispatch                     |
| Team familiarity (.NET)           | .NET                | MediatR + DI ecosystem reduces boilerplate; shorter ramp-up         |
| Small binary / container size     | Go                  | Distroless image ~15 MB vs ~120 MB for ASP.NET alpine               |
| Rich observability tooling        | .NET                | Built-in OpenTelemetry, dotnet-trace, Visual Studio profiler        |
| Rapid prototyping                 | .NET                | `dotnet new` scaffold + MediatR auto-wires commands                 |
| Long-running background consumers | Go                  | Goroutine-per-partition scales cheaply; no thread overhead          |
| Mixed command/query workloads     | .NET                | MediatR cleanly separates commands/queries with pipeline behaviours |