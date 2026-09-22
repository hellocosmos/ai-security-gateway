# Buffered SSE latency and rollout fit — 0.44

[en](../en/latency.md) · [ko](../ko/latency.md) · [zh-CN](../zh-CN/latency.md) · [ja](../ja/latency.md) · [es](../es/latency.md) · [fr](../fr/latency.md)

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
