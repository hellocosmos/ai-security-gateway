# TrapDefense — AI Security Gateway (0.46)

> [Model provider connections](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

[en](../en/aisg.md) · [ko](../ko/aisg.md) · [zh-CN](../zh-CN/aisg.md) · [ja](../ja/aisg.md) · [es](../es/aisg.md) · [fr](../fr/aisg.md)

Connect supported HTTP APIs and remote MCP servers through one explicit security boundary. Add agent identity when you need per-agent control.

## Connect, identify, control, verify

Deploy the Docker fixture, register an agent in Access Broker, enable autonomous access for selected tools, and issue a credential. Change the client endpoint and send the credential in the Authorization header. Test one allowed call and one denied call, then inspect the decision evidence.

## Choose your identity model

Gateway access uses a deployment key or verified JWT. Local agent_key mode identifies a registered agent without an external IAM. JWT identity_mode: agent uses verified tenant/agent claims; delegated mode additionally requires user, task and delegation. Existing agents require delegation by default.

## Credential lifecycle

Local credentials expire after 1 hour, 24 hours or up to 30 days. Only their hashes are stored. The console displays a new credential once. Rotation immediately revokes the old key; revocation and disabling the agent block subsequent authentication. Gateway credentials are never target-service credentials.

## Compatibility and limits

One fixed destination per installation; explicitly mapped HTTP JSON and stateless MCP JSON POST. The generic HTTP/MCP profile has no SSE, stateful sessions, stdio, WebSocket or closed SaaS-internal calls. Opt-in [model provider profiles](providers.md) support bounded, fully inspected SSE with buffered delivery. A model API base_url change does not route separately executed tools. Configure each protected tool/API endpoint and prevent bypass with customer network controls.

## Approvals

Autonomous access checks allowed tools, resources and actions. High-risk actions still require an expiring, request-bound approval. Retry the same local-key request with X-TD-Approval-ID after review; execution consumes the approval once. Mirror evaluation does not create or consume approvals.

## Evidence

Local synthetic verification is not production IdP, customer routing, HA or capacity certification. Access Broker remains experimental. No managed cloud signup is available.

## Quick start

```bash
cd deploy/selfhost
docker compose -f compose.yaml -f compose.agent.yaml build app
docker compose -f compose.yaml -f compose.agent.yaml run --rm app init
docker compose -f compose.yaml -f compose.agent.yaml --profile smoke up -d
```

Console: `http://localhost:18080` · Gateway: `http://localhost:18084`

```text
API base_url: http://localhost:18084
MCP URL: http://localhost:18084/mcp
Authorization: Bearer <agent-credential>
```


```bash
# Set TD_AGENT_CREDENTIAL locally to the credential displayed once in the console.
# Register notes.read and enable autonomous access first.
curl --fail-with-body http://localhost:18084/api/notes \
  -H "Authorization: Bearer ${TD_AGENT_CREDENTIAL}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'

# Expected: HTTP 403. The fixture policy blocks notes.delete.
curl --fail-with-body http://localhost:18084/mcp \
  -H "Authorization: Bearer ${TD_AGENT_CREDENTIAL}" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"notes.delete","arguments":{}}}'
```

[Self-hosting](self-hosting.md) · [Identity](identity.md) · [Compatibility](gateway-compatibility.md)
