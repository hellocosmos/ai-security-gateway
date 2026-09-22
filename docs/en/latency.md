# Buffered SSE latency and rollout fit — 0.46

[en](../en/latency.md) · [ko](../ko/latency.md) · [zh-CN](../zh-CN/latency.md) · [ja](../ja/latency.md) · [es](../es/latency.md) · [fr](../fr/latency.md)

## 0.46: bounded admission and optional process capacity

`gateway_admission_wait_ms` accepts 0–2000 ms and defaults to 0 (immediate HTTP 503 when full). With a positive wait, at most `gateway_max_inflight` authenticated callers can wait for a slot; overflow and timeout return HTTP 503 **before** the body is read or the target is called. The gateway never retries an admitted call, including non-idempotent tool actions.

`inspector_replicas` accepts 1, 2 or 4 and defaults to 1. Values 2 and 4 start supervised inspector processes on this Docker host; Envoy distributes inspection streams across healthy processes and still fails closed if inspection is unavailable. This is process capacity, not cross-host HA. Worker loss can fail an in-flight request; clients must not blindly retry an action whose destination outcome is unknown.

Configure these fields in `deploy/selfhost/deployment.yaml`, stage/activate changes with the [self-hosting procedure](self-hosting.md), and qualify the result on the target host. In multi-process mode, the console's request timeline and distributions cover the gateway process only; inspector timing fields are unavailable. No throughput or first-content improvement is guaranteed by the setting alone. Full-response buffering remains in place.

The gateway collects and inspects the complete supported response before delivering content. Client first-content latency includes collection and inspection, not just scanner time. This suits workflows that can wait for a complete result; interactive chat must be tested against an explicit latency budget.

## Reproduce

Requires Docker, Python 3.11+ and the project console dependencies. The command builds one disposable stack, uses no live credentials or paid API, and removes its containers and volumes in finally. Run on an otherwise idle host at least three times before making deployment decisions.

```bash
python -m pip install -e ".[console,compat,llm-compat]"
python -m examples.latency.benchmark --output /tmp/latency.json
```

## First-content p95 / completion p95 (ms)

2026-09-22 · synthetic fixture · short: 8 × 65 bytes content; long: 32 × 515 bytes content · 20 ms/chunk.

| Scenario | Concurrency | Direct | Gateway |
|---|---:|---:|---:|
| short | 1 | 56 / 202 | 232 / 233 |
| short | 8 | 58 / 197 | 420 / 421 |
| short | 32 | 97 / 219 | 1253 / 1253 |
| long | 1 | 53 / 752 | 822 / 822 |
| long | 8 | 69 / 745 | 1164 / 1164 |
| long | 32 | 89 / 726 | 3014 / 3014 |

This is one synthetic run on Docker ARM64 with 14 allocated CPUs and 7.75 GiB memory, not minimum hardware or a user-count capacity claim. Each matrix cell has 12–64 samples; p95 is descriptive, not an SLA. Direct calls use TLS; the local gateway client uses HTTP and its upstream uses TLS. No real-model run was performed for 0.44 because no provider credential was configured. Previous live-model evidence remains separately dated.

## Interpretation

The operations console shows the last 256 samples per phase in the current process. Gateway time ends when the buffered response is ready, before client delivery. Envoy exchange includes request inspection, upstream collection, response inspection and transport. Inspection phases include worker queue wait. Distributions include failures, are not per-request correlated, cannot be subtracted, and reset on restart. Empty samples are unmeasured, not zero.

## Boundaries

The 64-request burst completed 32 and rejected 32 with HTTP 503; no incomplete HTTP 200 SSE responses. Split email PII was redacted. With the test-only 32 KiB limit, oversized output returned HTTP 500 with no content token; a 10-second upstream timeout returned 504 with no content token. Invalid credentials returned 401. Status alone does not identify the failing component. Production defaults differ.

## Evidence limits

[JSON](../evidence/latency-044-synthetic.json) · [Operations guide](operator-workspace.md)


| Docker sampled resource | Peak CPU (100% = one core) | Peak memory (MiB) |
|---|---:|---:|
| App / Python inspector | 87.8% | 148.9 |
| Envoy | 3.91% | 37.38 |
| Synthetic fixture | 17.87% | 21.77 |

These are sampled peaks across the entire run, not per-scenario reservations or hardware recommendations. Short peaks may be missed. The fixture runs on the same Docker host; this is not a controlled CPU-language comparison. Higher concurrency increases queueing and inspection time, but this does not establish that Python is the cause or that Go/Rust would remove first-content buffering delay.

## Deployment decision

- Background/batch: accept only if measured completion p95 and error rate fit the job deadline at expected concurrency.
- Interactive chat: accept only if measured client first-content p95 fits the UX budget. The gateway currently buffers the response; do not advertise token-by-token delivery.
- Before rollout: repeat on the target host, use representative response sizes and policies, test burst rejection and recovery, and budget for upstream generation that may continue after client cancellation.
- No employee-to-hardware conversion is implied: active concurrency, response size, request rate, policy cost and deadlines determine load.

## 0.45 request timelines and admission

The operations console shows the last 64 completed gateway request timelines in the current process. Each row holds only numeric times, HTTP status and completion state. A signed random run ID joins adapter and inspector timing internally and is removed before display. No body, path, credential or agent identity is retained by this feature. Early authentication and admission failures appear in gateway outcomes instead.

Inspector stream wait, worker queue and execution are shown separately. The response body wait starts after metadata inspection and ends when the buffered body reaches the inspector. It includes upstream generation, transport and Envoy buffering. The stage intervals overlap or leave transport gaps; do not add them or call any one of them pure model latency. Records reset on process restart.

The optional `gateway_max_inflight` deployment setting accepts integers 4–64. The default remains 32. Apply a staged change with a maintenance restart; the connection wizard preserves the active setting. Extra requests receive HTTP 503. Choose a lower value only if less admitted traffic and lower latency fit the workflow. The local synthetic sweep at 48 introduced HTTP 500 outcomes without increasing successful burst completions.

No safe universal value follows from one synthetic run. Use the table below as a reproducible comparison, then qualify on the target host with representative responses, active concurrency, provider quotas and an explicit first-content/completion budget.

[Interactive streaming decision](interactive-streaming.md)

### Local synthetic sweep (2026-09-22)

Two repeats per setting used a 32-chunk delayed SSE fixture, a 32 KiB body limit, 16 inspector streams, and four inspection workers. Each concurrency-32 repeat sent 64 requests; each concurrency-64 repeat sent 128. The first-content p95 range is for completed HTTP 200 responses at concurrency 32, not all attempts.

| Gateway limit | Completed at concurrency 32 | First-content p95 | Completed at concurrency 64 | HTTP 500 at concurrency 64 | Sampled app peak CPU / memory |
|---:|---:|---:|---:|---:|---:|
| 8 | 8/64 each | 1.16–1.18 s | 8/128 each | 0 | 62% / 116 MiB |
| 16 | 16/64 each | 1.53–1.54 s | 16/128 each | 0 | 110% / 127 MiB |
| **32 (default)** | **64/64 each** | **3.02–3.10 s** | **32/128 each** | **0** | **118% / 148 MiB** |
| 48 | 64/64 each | 2.96–3.06 s | 32/128 each | 13–16 | 124% / 161 MiB |

All non-200 attempts at limits 8–32 were HTTP 503, all successful responses were complete, and all four recovery requests per setting succeeded. The peak samples are descriptive and can miss short spikes. The 48-limit HTTP 500 cause was not isolated, so do not treat it as a diagnosed Python bottleneck. Buffered response delivery remains the dominant first-content tradeoff. [Raw evidence](../evidence/latency-045-synthetic.json) · Reproduce with `.venv/bin/python -m examples.latency.sweep --output docs/evidence/latency-045-synthetic.json`.
