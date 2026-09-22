# Local performance baseline

[English](../en/benchmark.md) · [한국어](../ko/benchmark.md) · [简体中文](../zh-CN/benchmark.md) · [日本語](../ja/benchmark.md) · [Español](../es/benchmark.md) · [Français](../fr/benchmark.md)

This command measures a reproducible **synthetic local baseline** through the installed Envoy listener, gRPC ExtProc inspector and synthetic HTTP destination. It is for comparing revisions on the same host. It is not a production capacity, HA or customer traffic certification.

## Run

Install once with `./scripts/install-console.sh`, then stop the console because the benchmark owns the same loopback ports.

```bash
.venv/bin/trapdefense-benchmark --scenario read --iterations 30
```

Scenarios are `read`, `pii`, `secret` and `response`. Iterations are bounded from 5 to 500 and warmup from 0 to 50. The default is 30 measured requests after 3 warmups. Each measured request traverses the proxy and produces sanitized decision evidence; no external business destination or model API is used.

## Interpret the JSON

Use `p50_ms`, `p95_ms`, `mean_ms` and `sequential_requests_per_second` only as a local regression reference. Outcome and HTTP-status counts confirm that measurement did not silently change the expected decision. The report includes OS, architecture, Python version and logical CPU count, but excludes hostname and inspected content.

Compare results only when host load, Docker version, power mode, scenario, iteration count and policy are equivalent. Run at least three times and retain the median run. Parallel capacity, connection reuse, large bodies, sustained SSE, failure recovery and multi-node behavior require separate benchmarks.

See the [console guide](console.md), [architecture](architecture.md), [editions](editions.md) and [security scope](security.md).

## Same-host inspector pool

[Same-host inspector pool](inspector-pool.md)

## 0.44 · Buffered SSE

[Buffered SSE latency and rollout fit](latency.md)

The gateway collects and inspects the complete supported response before delivering content. Client first-content latency includes collection and inspection, not just scanner time. This suits workflows that can wait for a complete result; interactive chat must be tested against an explicit latency budget.
