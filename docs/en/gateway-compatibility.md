# Gateway client compatibility — 0.45

> [Model provider connections](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [Connect, identify, control, verify](aisg.md). Gateway access uses a deployment key or verified JWT. Local agent_key mode identifies a registered agent without an external IAM. JWT identity_mode: agent uses verified tenant/agent claims; delegated mode additionally requires user, task and delegation. Existing agents require delegation by default.

[English](../en/gateway-compatibility.md) · [한국어](../ko/gateway-compatibility.md) · [简体中文](../zh-CN/gateway-compatibility.md) · [日本語](../ja/gateway-compatibility.md) · [Español](../es/gateway-compatibility.md) · [Français](../fr/gateway-compatibility.md)

TrapDefense exposes a normal remote HTTP/MCP endpoint. A client must let you replace its destination URL and send either a configured header or an OAuth Bearer token. Authentication from the client to TrapDefense stays separate from authentication from TrapDefense to the target.

```text
Client -- gateway credential --> TrapDefense -- target credential --> MCP / API
```

## Evidence matrix

| Client or flow | 0.42 status | Evidence and limit |
|---|---|---|
| Generic JSON HTTP client | **Synthetic integration verified** | HTTPX sends allowed and denied requests through the FastAPI adapter and fixed Envoy hop. |
| Official Python MCP SDK 1.30.0 | **Synthetic integration verified** | The unmodified SDK completes Streamable HTTP `initialize`, `notifications/initialized` and `tools/list` using MCP `2025-11-25`. |
| Entra-shaped OAuth | **Protocol-shaped synthetic verification** | The lab exercises `scp`, `tid`, `oid` and `azp` with discovery, DCR, authorization code, PKCE and RFC 8707 `resource`. This is not a real Entra tenant or proof of Microsoft-specific registration and policy behavior. |
| Okta-shaped OAuth | **Protocol-shaped synthetic verification** | The lab exercises an array-valued `scp` and `cid` through the same complete client flow. This is not a real Okta authorization server. |
| Keycloak-shaped OAuth | **Synthetic plus real local verification** | The claim profile is tested through the full lab. Separately, an unmodified digest-pinned Keycloak 26.7.3 container issues a real client-credentials token that TrapDefense verifies through its discovery and JWKS endpoints. |
| VS Code 1.135 remote MCP | **Real local client verified** | The installed product reports the server `Running`, discovers one tool and produces matching `initialize`, `notifications/initialized` and `tools/list` receipts. The client requested MCP `2025-11-25` during initialization. |
| Stateful MCP, long-lived SSE, WebSocket, stdio | **Unsupported** | Inbound and upstream `MCP-Session-Id` and upstream `text/event-stream` fail closed. This profile remains bounded stateless JSON over HTTP. |
| Multi-node HA | **Unsupported** | The package is one gateway instance with local SQLite, replay and audit state. Container restart recovery is not cross-server HA. |

Provider-shaped tests verify representative token syntax and standards flow. They do not reproduce each provider's application-registration API, tenant policy, Conditional Access, revocation, opaque-token mode or production TLS. A real customer tenant remains a deployment acceptance test.

## VS Code with a connection key

Use an input variable instead of committing a key to `.vscode/mcp.json`:

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "trapdefense-key",
      "description": "TrapDefense connection key",
      "password": true
    }
  ],
  "servers": {
    "trapDefense": {
      "type": "http",
      "url": "https://firewall.example.com/mcp",
      "headers": {
        "X-TD-Client-Key": "${input:trapdefense-key}"
      }
    }
  }
}
```

VS Code first tries Streamable HTTP for an HTTP MCP server. The repository includes a loopback fixture for exact-client acceptance, but configuration discovery alone is not a passing client result. Require matching server-side receipts for `initialize`, `notifications/initialized` and `tools/list` before approving a specific VS Code build.

Generate the ignored synthetic workspace and start the fixture in one terminal:

```bash
PYTHONPATH=src .venv/bin/python tests/compat/vscode_fixture.py \
  --workspace .runtime-state/vscode-compat/workspace \
  --receipts .runtime-state/vscode-compat/receipts.jsonl
```

Open `.runtime-state/vscode-compat/workspace` in the VS Code build under test, run **MCP: List Servers**, and start `trapdefense-compat`. A passing result shows `Running`, discovers `notes_read`, and contains server-side receipts for all three methods above. No GitHub or model-provider login is needed for server discovery.

VS Code 1.135 requested MCP `2025-11-25` in `initialize` but did not include `MCP-Protocol-Version` on the observed post-initialization requests. TrapDefense accepts the missing header, so this is verified interoperability rather than a claim that the client is fully transport-conformant. VS Code also rejects dots in tool names; use names matching `[a-z0-9_-]` for this client. When VS Code opens the optional GET stream, this stateless profile returns the standard `405 Method Not Allowed` with `Allow: POST` instead of triggering an OAuth fallback.

## JWT resource-server mode

```yaml
gateway_auth:
  mode: jwt
  issuer: https://login.example.com/tenant/v2.0
  audience: https://firewall.example.com/mcp
  jwks_uri: https://login.example.com/tenant/discovery/v2.0/keys
  resource: https://firewall.example.com/mcp
  authorization_servers:
    - https://login.example.com/tenant/v2.0
  required_scopes: [mcp.invoke]
  authorized_parties: [configured-client-id]

target_auth:
  mode: static_bearer
  secret_file: /run/secrets/target-token
```

The client sends a JWT issued for the TrapDefense resource. TrapDefense validates issuer, audience, time, subject and required scopes, optionally restricts the caller application through `azp`, `appid` or `cid`, and consumes the token. The configured target receives a separate target credential. The gateway JWT is never used as the target credential.

OAuth `scope` or `scp` may be a space-delimited string or string array. Entra application roles in `roles` are not treated as scopes in 0.42; use a delegated scope token or keep that flow outside the stated compatibility claim.

For MCP, a missing or invalid token returns `401` plus a gateway-owned `WWW-Authenticate` header pointing to RFC 9728 metadata. A valid token without every required scope returns `403`. TrapDefense publishes resource metadata but does not provide authorization, token, callback, registration, refresh or logout endpoints; the configured external authorization server owns those functions.

## Target credential modes

| Mode | Behavior |
|---|---|
| `none` | Sends no target credential. A client-key caller that submits `Authorization` is rejected rather than silently stripped. |
| `passthrough_bearer` | For legacy HTTP onboarding with `client_key` mode only. The caller's Bearer token reaches the fixed target. Do not describe this as MCP OAuth compliance. |
| `static_bearer` | Injects `Authorization: Bearer` from an owner-only file. A caller-supplied Authorization header is rejected. |
| `static_api_key` | Injects a file-backed value into a configured non-reserved header such as `X-API-Key` or `Ocp-Apim-Subscription-Key`. |

## Reproduce the compatibility evidence

```bash
.venv/bin/python -m pytest \
  tests/runtime/test_gateway_client_compat.py \
  tests/compat/test_oauth_provider_profiles.py -q

docker pull quay.io/keycloak/keycloak@sha256:29be7252db0a106f1cd2ac17b9a56ff2668073da645638a38b9fc67deeb2d6c4
TD_KEYCLOAK_E2E=1 .venv/bin/python -m pytest \
  tests/runtime/test_keycloak_compat.py -q -s
```

The Keycloak run uses only synthetic values, publishes the container on loopback and removes it after the test. The digest identifies the tested image even if the mutable vendor tag later changes.

## Acceptance checklist

Verify the exact client and service combination: endpoint replacement; gateway authentication; target authentication; MCP initialization/discovery if applicable; one allowed action; one denied action without target side effect; PII/secret handling; target `401`; inspection-path outage; and no direct-URL fallback. Inspect target logs and TrapDefense's sanitized evidence. Container health or a valid token alone is insufficient.

## Standards and vendor references

- [MCP Authorization Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [MCP Transports Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [VS Code MCP extension guide](https://code.visualstudio.com/api/extension-guides/ai/mcp)
- [Okta OAuth and OpenID Connect overview](https://developer.okta.com/docs/api/openapi/okta-oauth/guides/overview)
- [Keycloak Docker getting started](https://www.keycloak.org/getting-started/getting-started-docker)


The current qualification combines a live OpenAI model-to-synthetic-MCP workflow, official provider SDK fixtures, real local MCP/Keycloak paths and VS Code initialization/discovery evidence. Model SSE is buffered; stateful MCP, customer identity policy, cross-host HA and production capacity are not certified. See [0.42 workflow and limits](agent-workflow.md).
