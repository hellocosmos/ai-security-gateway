# TrapDefense — Open-source AI Security Gateway


[0.44: Buffered SSE latency and rollout fit](docs/en/latency.md)

## Least Privilege, Least Agency

**Least privilege limits access. Least agency bounds autonomous action.**

Our design principle: give an agent only the access it needs, and bound the actions it may take independently. TrapDefense complements existing IAM and destination permissions by enforcing action and data policies on supported calls routed through the gateway. Optional agent identity adds per-agent scopes, delegation and approval controls.

[0.44: Operator workspace (0.44)](docs/en/operator-workspace.md)


[0.42: Model → MCP → model verification](docs/en/agent-workflow.md)

**0.44:** [Model provider connections](docs/en/providers.md) — OpenAI · Anthropic · Gemini · OpenRouter.

**Connect supported HTTP APIs and remote MCP servers through one explicit security boundary. Add agent identity when you need per-agent control.**

[Connect, identify, control, verify →](docs/en/aisg.md)

[![Open source verification](https://github.com/hellocosmos/ai-security-gateway/actions/workflows/test.yml/badge.svg)](https://github.com/hellocosmos/ai-security-gateway/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-2563EB.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-0F172A.svg)](pyproject.toml)
[![Status: Open Source Preview](https://img.shields.io/badge/status-Open%20Source%20Preview-F59E0B.svg)](docs/en/editions.md)

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Français](README.fr.md)

> **Open Source Preview 0.44:** the full runtime and operator experience are MIT licensed. The built-in Agent Access Broker is implemented and synthetically verified, but remains **Experimental** until production IdP, customer policy, HA, and capacity validation are complete.

**Control the path from model intent to real action.**

TrapDefense is a self-hosted AI Security Gateway for supported HTTP and MCP traffic. It inspects requests and responses, enforces explicit action and data policy, records sanitized evidence, and can authorize an action against a registered agent, delegation, task, resource, and one-time human approval.

```text
AI agent / client
  → authenticated gateway
  → trusted request binding
  → Envoy + request/response inspection
  → optional built-in Agent Access Broker
  → configured tool, MCP server, or HTTP API
```

The earlier embedded SDK remains available in [agent-runtime-security](https://github.com/hellocosmos/agent-runtime-security). This repository is the proxy product and requires no private runtime package.

## Console in action

Actual 0.41 screens with synthetic data. The dashboard includes a deliberate seven-second provider delay test; these numbers are not a performance benchmark. Agent management is shown in a separate local demo.

![Runtime dashboard](docs/assets/console-dashboard-041.png)

<table>
<tr>
<td width="50%"><img src="docs/assets/console-agents-041.png" alt="Agent permissions · Experimental"><br><strong>Agent permissions · Experimental</strong></td>
<td width="50%"><img src="docs/assets/console-provider-041.png" alt="Provider connection settings"><br><strong>Provider connection settings</strong></td>
</tr>
</table>

## One open-source product

There are no Community and Enterprise code editions. This repository contains:

- Runtime Gateway for explicitly mapped HTTP and stateless MCP JSON POST calls;
- request and response PII/secret inspection with inline and mirror policy semantics;
- trusted-hop signatures, exact request digest binding, nonce/replay protection, and sanitized audit evidence;
- external OAuth JWT validation and an explicit JWT-claim-to-agent-identity map;
- Agent Registry, task delegation, resource/action authorization, and request-bound one-time approval;
- local operations console, six UI languages, Docker Compose self-hosting, and same-host inspector supervision.

Future paid work can provide a managed cloud service, fleet operations, multi-node HA, immutable external audit storage, customer integrations, and support. The open-source runtime does not hide current enforcement features behind a license gate. See [One open-source product](docs/en/editions.md).

## Docker self-hosting · 0.44

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
```

Open `http://localhost:18080`, sign in as `admin` with the password chosen during initialization, and inspect the synthetic fixture. No default password is created by the Docker profile.

A client must support a configurable HTTP/MCP endpoint and either `X-TD-Client-Key`, a local agent Bearer credential, or a Bearer JWT. Target credentials are separate. One installation uses one fixed destination origin and explicit route/tool mappings. Stateful MCP, unbounded SSE, WebSocket, arbitrary CONNECT, binary uploads, stdio, direct database access, and closed SaaS-internal calls are outside this profile.

[Self-hosting and exact integration contract](docs/en/self-hosting.md) · [Gateway compatibility evidence](docs/en/gateway-compatibility.md) · [Deployment fit](docs/en/deployment-fit.md)

## Optional Agent Access Broker (Experimental)

Gateway-only mode verifies the forwarding source and applies local inspection policy. It does not claim agent identity.

Broker mode supports local `agent_key` credentials or external JWTs with an explicit claim map. Autonomous authorization checks registered agent tools, resources and actions; delegated authorization also requires user, task and delegation. Existing records remain delegated-only. Missing identity fails before forwarding. See the [AISG connection guide](docs/en/aisg.md).

```yaml
gateway_auth:
  mode: jwt
  issuer: https://login.example.com/tenant/v2.0
  audience: https://firewall.example.com/mcp
  jwks_uri: https://login.example.com/tenant/discovery/v2.0/keys
  resource: https://firewall.example.com/mcp
  authorization_servers: [https://login.example.com/tenant/v2.0]
  required_scopes: [mcp.invoke]
  identity_claims:
    tenant_id: tid
    user_id: sub
    agent_id: agent_id
    delegation_id: delegation_id
    task_id: task_id
    agent_instance_id: agent_instance_id
    approval_id: approval_id

access_broker:
  enabled: true
  tenant_id: tenant-a
```

In delegated mode the built-in broker checks tenant, agent registry, tool/resource scope, delegation, user, task, action, request digest, and optional approval. High-risk actions produce `approval_required`. An approved request can be consumed once and cannot be replayed for a different request, agent instance, tenant, user, task, or action.

TrapDefense is an OAuth resource server in this path. It does not issue IdP tokens or replace target-service authorization. The broker token is decision evidence, not a downstream OAuth credential.

## Local source demo

Requires Python 3.11+, Node.js 22.12+ (or 24), npm, and Docker Engine/Desktop.

```bash
./scripts/install-console.sh
./scripts/run-console.sh
```

Open [http://127.0.0.1:5176](http://127.0.0.1:5176), sign in with `admin` / `1234`, then change the password in Settings. The source demo seeds synthetic agents and delegations into the real file-backed Access Broker. The deployment scenario demonstrates `approval_required → approve → one matching execution → replay blocked` through the same authorization code shipped for self-hosting.

The demo uses synthetic identities and tools. It does not prove a production Entra, Okta, or Keycloak tenant, Conditional Access, customer MCP authentication, enforced customer routing, HA, or production capacity.

## Security boundaries

| Boundary | Enforced behavior |
|---|---|
| Routing | Only traffic sent through the configured gateway is inspected. Prevent bypass outside TrapDefense. |
| Gateway authentication | Deployment key, local agent credential or verified JWT admits a caller to a fixed set of routes. |
| Trusted hop | HMAC attestation binds the adapter, application headers, request body, and final request digest. It is not agent identity. |
| Content policy | Supported requests and responses can be allowed, blocked, or redacted. Unknown/incomplete inline inspection fails closed. |
| Agent authorization | Optional broker checks registered identity and delegated action scope. Mirror evaluation never creates approvals, tokens, or audit mutation. |
| Target authorization | The destination still enforces its own credential and permissions. Gateway JWTs are not forwarded as target credentials. |
| Evidence | Local JSON/SQLite files omit original protected content where designed, but remain mutable local storage. |

Read [Architecture](docs/en/architecture.md), [Security](docs/en/security.md), and [Identity](docs/en/identity.md) before connecting a real service.

## Verified evidence

The repository tests cover the broker's tenant isolation, deny-by-default scopes, strict request digest, approval expiry and replay protection, transactional local file store, concurrent approval consumption, JWT issuer/audience/scope/authorized-party checks, explicit identity mapping, gateway/target credential separation, HTTP/MCP mapping, PII and secret controls, and console operations.

The compatibility lab exercises Entra-, Okta-, and Keycloak-shaped OAuth claims, an unmodified Keycloak container, the official MCP SDK, and VS Code MCP initialization/tool discovery. These are reproducible synthetic/local protocol results, not certification of a customer tenant.

```bash
pip install -e ".[dev]"
pytest -q
npm run check --prefix console
npm run build --prefix console
```

For the optional real local Envoy path, stop any running console and run:

```bash
TD_CONSOLE_E2E=1 .venv/bin/python -m pytest tests/test_console.py -q
```

## Documentation

[Console](docs/en/console.md) · [Architecture](docs/en/architecture.md) · [Open-source model](docs/en/editions.md) · [Self-hosting](docs/en/self-hosting.md) · [Gateway compatibility](docs/en/gateway-compatibility.md) · [Benchmarking](docs/en/benchmark.md) · [Migration](docs/en/migration.md) · [Security](docs/en/security.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

English is the source language. The console and core guides are maintained in English, Korean, Simplified Chinese, Japanese, Spanish, and French.

## License

MIT. All runtime enforcement and Access Broker code in this repository is open source.
