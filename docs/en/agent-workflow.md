# Model → MCP → model workflow (0.44)

[English](../en/agent-workflow.md) · [한국어](../ko/agent-workflow.md) · [简体中文](../zh-CN/agent-workflow.md) · [日本語](../ja/agent-workflow.md) · [Español](../es/agent-workflow.md) · [Français](../fr/agent-workflow.md)

Run an official OpenAI Python SDK client and the official MCP client through **two independent gateway deployments**. A model API base URL change protects model traffic; the MCP URL must also point to its gateway to protect tool execution.

```text
Agent A / Agent B
  ├─ OpenAI SDK → model Gateway → Envoy + inspector → model API
  └─ MCP client → tool Gateway  → Envoy + inspector → synthetic business MCP
             model proposal → authorized tool execution → inspected result → model
```

Each deployment has one fixed origin, its own state, and its own credentials. The same agent ID is registered on both gateways, but **its two access keys are different**. Provider and MCP destination keys stay on their gateways. The example does not turn a provider key into agent identity, share keys between deployments, or provide a central fleet registry.

## Reproduce without a provider account

Requirements: Python 3.11+, Docker Engine/Desktop with Compose, `openssl`, and the source repository. Run from its root without sudo.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,console,compat,llm-compat]'
python -m examples.agent_workflow --report .runtime-state/workflow-042.json
```

Choose a new report filename for subsequent runs. The runner builds the existing self-hosted image, creates two uniquely named Compose projects with random loopback ports, initializes disposable credentials, runs the checks, and removes its own containers/volumes in `finally`. It does not stop an existing installation. No UI build tool is needed on the host: Docker builds the console.

In default mode, the model is **scripted**, with no real inference or paid API request. The official SDK speaks native Chat Completions to a private TLS fixture through the real gateway and Envoy. Only the test model stack trusts the temporary fixture CA; system trust is unchanged. The MCP fixture implements a narrow stateless initialize/discovery/call contract and runs on its private Docker network. It is a synthetic target, not a production connector.

## Expected evidence

| Check | Required result |
| --- | --- |
| Agent A reads a customer note | Model proposes `notes_read`; MCP succeeds; model receives the inspected result and completes a second turn |
| Agent B attempts the same read | Broker records `tool_not_allowed_for_agent`; no read reaches the destination |
| Agent A attempts deletion | Route policy records `local_policy_denied`; no deletion reaches the destination |
| PII in model/tool traffic | Synthetic email is redacted; destination receipts contain no raw email |
| Previously successful Agent A keys are revoked | Both model and MCP gateways return HTTP 401 for the old keys |
| Expired credential fixture | Both gateways return HTTP 401; expiry is seeded into the past, not a wall-clock duration benchmark |

The report contains sanitized statuses, tool names, turn counts, enforced block reasons and destination receipt counts. It does not contain access keys, prompts, raw model answers or customer records. Passing requires both enforcement evidence and actual destination receipts. Discovery or model failures are not accepted as successful policy blocks. No tool proposal, unexpected tools, invalid arguments and repeated calls fail the workflow.

The tool fixture receives exactly two reads (one agent workflow and one independent request-redaction probe), zero deletions, and no raw synthetic email. The scripted model receives three inspected tool-result turns. This is protocol/authorization evidence, **not proof of real-model planning**.

## Optional live OpenAI validation

The live path uses the same two gateways and synthetic MCP data, but connects the model gateway to the actual OpenAI HTTPS origin. No synthetic fallback occurs if the live model fails.

1. Choose an available OpenAI model that supports Chat Completions function calling.
2. Put a dedicated, restricted test API key in an owner-only file outside the repository (`chmod 600`). Never paste it into a command argument or commit it.
3. Run explicitly:

```bash
python -m examples.agent_workflow \
  --model YOUR_MODEL_ID \
  --provider-key-file /absolute/private/provider-key \
  --report .runtime-state/workflow-042-live.json
```

This makes billable API calls and sends only the example's synthetic tasks and inspected tool outputs. Maximum four model requests per scenario, three scenarios, 512 requested completion tokens per request, no automatic retries. It is a bound on requests/tokens, not a guaranteed price ceiling. The key is read locally and passed to the gateway initialization through stdin; it is not passed in process arguments or Docker environment variables. The temporary model volume stores the key until cleanup.

A live pass requires the model to actually exercise the requested read/delete tools and finish after seeing success/denial. If the model refuses, skips a tool, repeats an action or emits an unsupported response, the run fails rather than presenting synthetic results as live evidence. Final-answer wording is not semantically graded; execution evidence is authoritative.

**Current qualification (2026-09-18):** the live OpenAI `gpt-4.1-mini` workflow passed all three scenarios, with two model turns each, through Docker and Envoy. MCP business data and the destination remain synthetic. This is one model/account qualification, not certification of all providers or production environments. Native LLM response cookies are discarded before inspection and forwarding. Bounded native Chat Completions and OpenAI Responses creation timestamps, including supported SSE envelope paths, are treated as protocol metadata; nested business fields remain inspected.

## Failure and scope

- The agent loop uses discovered JSON schemas, four model turns and eight total calls as hard bounds. It sends tools only to the configured loopback MCP gateway; tool names/arguments cannot choose an arbitrary network destination.
- A failed run exits nonzero and writes no success report. If cleanup reports an owned project name, inspect it with `docker ps --filter label=com.docker.compose.project=PROJECT`; remove only that test project's resources after inspection.
- Synthetic MCP data, HTTP inside the isolated tool network, localhost clients, single-host file stores: this is a verification example, not a production deployment blueprint or HA claim.
- Uses ordinary bounded responses. Real-time token streaming, disconnect cancellation and Go/Rust performance changes are outside 0.42.
- Existing [provider profile limits](providers.md), [identity boundaries](identity.md), and [self-hosting requirements](self-hosting.md) still apply.

Focused checks:

```bash
pytest tests/test_agent_workflow.py -q
TD_AGENT_WORKFLOW_E2E=1 pytest tests/runtime/test_agent_workflow_runtime.py -q -s
```


## 0.42 extended qualification

- The scripted Docker workflow includes duplicate response cookies and a realistic timestamp. Actual Envoy header removal is checked; non-LLM routes, Mirror Mode and nested business fields keep their inspection behavior.
- Official Python provider SDK fixtures cover OpenAI, Anthropic, Google and OpenRouter, ordinary JSON and supported buffered SSE. Only the separately recorded OpenAI `gpt-4.1-mini` workflow used a live provider account.
- A real local MCP SDK server exercised document lifecycle, action controls and inspector outage. This is not a customer ERP, SaaS or customer MCP deployment.
- Same-host inspector supervisor tests exercised worker restarts, replay persistence, exhausted recovery and all-workers-down failure. This is not cross-host HA: shared authorization state and failover across servers are not qualified.

### Bounded local load observation

Mac ARM64, Docker, one gateway with per-agent authorization and synthetic MCP, five seconds per row. One hypothetical user generates 0.1 requests/second; 10% are policy-denied deletes and 10% carry a synthetic email. Latency includes scheduling delay. These short observations are not recommended hardware sizing or sustained capacity guarantees. The load generator and gateway share the host.

| Hypothetical users | Offered RPS | Message size | Expected outcomes / requests | HTTP 503 | Scheduled p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 100 | 10 | 1 KiB | 50 / 50 | 0 | 40 ms |
| 300 | 30 | 1 KiB | 150 / 150 | 0 | 49 ms |
| 500 | 50 | 1 KiB | 185 / 250 | 65 | 1,077 ms |
| 1,000 | 100 | 1 KiB | 128 / 500 | 372 | 1,654 ms |
| 500 | 50 | 64 KiB | 99 / 250 | 151 | 2,023 ms |

No denied delete reached the destination and no synthetic email leaked in requests or responses in these samples. **Overload rejected traffic; higher completed-response counts include errors and must not be read as successful throughput.** Tune and measure the actual deployment before choosing a concurrency or availability target.

Customer MCP endpoints, other live provider accounts, real-time token delivery and cross-host HA remain outside this qualification. No credentials are included in the repository or reports.


### Buffered SSE and client timeout

An actual Docker/Envoy test used a synthetic TLS provider emitting an email in two delayed SSE chunks. The gateway delivered the first body bytes after 1.061 seconds, after whole-stream inspection, with the reassembled email fully masked and the terminal event preserved. A separate 0.2-second client timeout did **not** stop the synthetic provider: it completed upstream. This qualifies buffering and split-PII inspection, not real-time delivery or guaranteed generation cancellation. Budget for provider work that may continue after client abandonment.
