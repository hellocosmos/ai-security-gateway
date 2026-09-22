# Docker self-hosting (0.46 Open Source Preview)

> **0.44:** [Operator workspace (0.44)](operator-workspace.md)


> [Model provider connections](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [Connect, identify, control, verify](aisg.md). Gateway access uses a deployment key or verified JWT. Local agent_key mode identifies a registered agent without an external IAM. JWT identity_mode: agent uses verified tenant/agent claims; delegated mode additionally requires user, task and delegation. Existing agents require delegation by default.

[English](../en/self-hosting.md) · [한국어](../ko/self-hosting.md) · [简体中文](../zh-CN/self-hosting.md) · [日本語](../ja/self-hosting.md) · [Español](../es/self-hosting.md) · [Français](../fr/self-hosting.md)

**0.46 capacity controls:** `gateway_admission_wait_ms` (default 0, maximum 2000) permits a short, finite wait before an authenticated call enters the gateway; `inspector_replicas` (default 1; optional 2 or 4) runs supervised inspectors on this host. Apply through the existing stage/activate and restart procedure. See [latency and failure semantics](latency.md) before changing either value. This is not HA and does not enable automatic retries.

## Choose your 0.44 starting point

- **Model APIs:** use a [provider profile](providers.md) for OpenAI, Anthropic, Gemini or OpenRouter. Change the native SDK base URL; put the provider key on the gateway.
- **HTTP / MCP tools:** follow the Docker quickstart below, then replace the synthetic destination with an explicitly mapped service.
- **End-to-end evaluation:** run the [two-agent model → MCP → model example](agent-workflow.md). Default mode needs no paid model key; the guide separates live OpenAI evidence from synthetic tests and lists measured limits.

Gateway authentication supports `client_key`, `agent_key` and external `jwt`. Optional agent identity adds scope checks; it does not replace destination authentication. Each deployment has one fixed origin. Route the model and separately executed tools through their own gateway deployments.

## Start here: does your client fit?

This package supports **one fixed destination origin per installation** and an explicit list of HTTP routes/MCP actions. The client must let you change its API/MCP URL and use either `X-TD-Client-Key`, a local agent Bearer credential, or an OAuth Bearer JWT. Target credentials remain separate. Use a server-side client or a separately configured same-origin application; this package does not enable permissive browser CORS. If the required settings are unavailable, this package is not a drop-in integration for that client. See the [gateway compatibility matrix](gateway-compatibility.md).

```text
Client -- connection key, agent key or JWT --> bundled adapter
       -- separate target credential --> private Envoy --> inspector --> configured MCP / HTTP API
       <-- inspected, bounded response <--
Operator --> console login --> policies and sanitized decision records
```

The bundled adapter verifies the connection key or individual agent credential or configured JWT issuer/audience/scope, removes submitted forwarding identities, binds the actual request to a private signature and forwards only through Envoy. Clients never receive the signing key. `source_verified` means this trusted forwarding path was verified; it does **not** prove the user's or agent's identity. A validated JWT authenticates gateway access. It creates broker identity only when `identity_claims` is configured and the built-in Access Broker is enabled.

## What works, and what does not

| Connection | Package contract | Customer changes |
|---|---|---|
| Model provider APIs | Native text/function calls and fully buffered SSE via [provider profiles](providers.md) | Change SDK base URL; configure provider key, profile and model allowlist |
| JSON HTTP API | Exact method/path mapping; bounded request/response; fixed origin | Change base URL; set connection key; define route/action/resource and redaction fields |
| Remote MCP | Stateless JSON POST; explicitly mapped control methods and tools | Change MCP URL; use client key or OAuth JWT; server must return JSON and not require sessions |
| Local agent key | Registered agent identity, expiry/revocation and broker scope checks | Enable `agent_key` and Access Broker; register an agent and issue its credential |
| Gateway JWT | RS256, issuer, audience, time, subject and scope validation; RFC 9728 metadata and gateway challenge | Register TrapDefense as a resource in the external IdP; acquire tokens outside TrapDefense |
| Existing target Bearer | `passthrough_bearer` with client-key mode only; legacy HTTP onboarding, not MCP OAuth compliance | Target validates the token; acquire and refresh it outside TrapDefense |
| Fixed target credential | `static_bearer` or `static_api_key` injects a private file-backed credential; conflicting inbound credentials are rejected | Mount a secret file, rotate it and recreate the app; every allowed caller shares this service identity |
| Console login | Locally initialized `admin`; password changes revoke sessions | Set a unique password during initialization |
| Entra console SSO | Existing source-console capability; **not wired into this Docker profile** | See [identity guide](identity.md); never interpret console SSO as agent authorization |
| OAuth login/token exchange/DCR/OBO, Basic auth | **Not provided by this profile**; an external authorization server owns OAuth issuance and the target challenge is not relayed | Use a supported IdP/credential provider and validate the complete client flow |
| Stateful MCP, MCP SSE, cookie sessions, WebSocket, uploads/binary content | **Not supported by the generic HTTP/MCP profile** | Model profiles separately support bounded buffered SSE; no real-time token delivery |
| stdio, shell, local files, direct DB or closed SaaS-internal calls | Outside this proxy's visibility | Not covered |

In JWT mode, TrapDefense is an OAuth resource server, not an authorization server. It validates a token issued for the configured TrapDefense audience and does not forward that token to the target. Target services still enforce their own permissions using an independent credential. A client key or unmapped JWT subject is not an agent registry, delegation record or per-agent IAM.

## Fresh installation

Prerequisites: Git and Docker Engine/Desktop with Compose v2. Python and Node run inside the build. This builds a local image; no hosted image registry or managed Cloud availability is implied. Allocate enough memory for dependency installation and inspection; measure your workload before sizing production.

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
# Choose and confirm a unique 12+ character administrator password.
docker compose --profile smoke up -d
```

The checked-in configuration targets the **synthetic fixture** enabled by `--profile smoke`. Do not mistake this for a real SaaS integration. Open `http://localhost:18080`, sign in as `admin` with your chosen password, and open Connections / System. No `admin / 1234` account is created in this mode. The source demo remains separate.

Read the deployment connection key deliberately and store it as a secret:

```bash
docker compose run --rm app client-key
```

Do not put the key in URLs, issue reports or logs. Set it in your client's secret/header configuration. The separate administrator password does not authenticate agent traffic.

## First request and negative checks

For the synthetic fixture only, the destination credential is `Bearer synthetic-target-token`. Avoid entering real tokens into shell history. For this local test, read the connection key without echoing it:

```bash
read -r -s TD_CLIENT_KEY
export TD_CLIENT_KEY
curl -sS http://localhost:18084/api/notes \
  -H "X-TD-Client-Key: $TD_CLIENT_KEY" \
  -H 'Authorization: Bearer synthetic-target-token' \
  -H 'Content-Type: application/json' \
  --data '{"message":"Summarize the notes"}'
```

Expected: HTTP 200 and a new decision record in the console. Replace the message with `Contact alex@example.com`: permitted fields should be redacted. Omit the connection key: HTTP 401 before forwarding. Use the connection key but a wrong service token: destination HTTP 401. These are two different authentication failures.

MCP action example:

```bash
curl -sS http://localhost:18084/mcp \
  -H "X-TD-Client-Key: $TD_CLIENT_KEY" \
  -H 'Authorization: Bearer synthetic-target-token' \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"notes.delete","arguments":{}}}'
```

Expected: blocked by the configured action policy. The optional fixture is a small synthetic protocol target, not proof of a particular MCP vendor. 0.42 runs the pinned official Python MCP SDK through the adapter for current-protocol initialization and discovery; see [gateway compatibility](gateway-compatibility.md). The broader [MCP pilot](mcp-pilot.md) remains a separate tool-operation path.

## Connect your own destination

1. Stop the smoke stack with `docker compose --profile smoke down` (without `-v`).
2. Edit `deployment.yaml`: replace `upstream`, each route's `authority`, exact paths, methods, tool/action/resource mappings and allowed redaction fields. Use a DNS HTTPS origin, for example `https://api.example.com`; no URL credentials, base path, query or fragment. Certificate-chain and hostname checks are enabled. For a private CA, mount the appropriate CA bundle into Envoy at `/etc/ssl/certs/ca-certificates.crt`; never disable verification.
3. Plain HTTP requires `allow_plaintext_upstream: true`; use it only on an explicitly trusted segment. One installation cannot dynamically select destinations based on client URLs. Deploy separate instances for different origins.
4. Configure `gateway_auth` as `client_key`, `agent_key` or `jwt`. Configure `target_auth` as `none`, `passthrough_bearer`, `static_bearer` or `static_api_key`. JWT and agent_key cannot be combined with passthrough. For static modes, mount the secret file read-only into the app, readable by UID 10001 and mode 0600. Do not commit secret files. Restart the app after rotation. Conflicting caller credentials are rejected.
5. If route/tool keys changed after initialization, explicitly migrate saved policies using the procedure below. Existing saved policies are never silently replaced by new YAML defaults.
6. Run `docker compose run --rm app render` and `docker compose up -d --force-recreate` (without the smoke profile). Change the client's URL to your gateway and add its connection key. Send an allowed and blocked request; examine destination-side effects and console evidence.

Example static-token override (create a private local Compose file):

```yaml
services:
  app:
    volumes:
      - ./destination.secret:/run/secrets/destination:ro
```

Corresponding target configuration:

```yaml
target_auth:
  mode: static_bearer
  secret_file: /run/secrets/destination
```

JWT gateway configuration:

```yaml
gateway_auth:
  mode: jwt
  issuer: https://login.example.com/tenant/v2.0
  audience: https://firewall.example.com/mcp
  jwks_uri: https://login.example.com/tenant/discovery/v2.0/keys
  resource: https://firewall.example.com/mcp
  authorization_servers: [https://login.example.com/tenant/v2.0]
  required_scopes: [mcp.invoke]
  authorized_parties: [configured-client-id]
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
target_auth:
  mode: static_bearer
  secret_file: /run/secrets/destination
```

Production identity and metadata URLs require HTTPS. `allow_insecure_loopback: true` exists only for explicit local synthetic tests. The resource-derived metadata URL for the example is `https://firewall.example.com/.well-known/oauth-protected-resource/mcp`. `authorized_parties` is optional; when configured, the token must carry a matching `azp`, `appid` or `cid` client identifier. Scope validation accepts the OAuth `scope`/`scp` claim as a space-delimited string or string array. Entra application roles in `roles` are not treated as scopes in 0.42.

`identity_claims` is an explicit allowlist. The broker-enabled gateway copies only those verified claims into the signed inspector context. In the default delegated JWT mode, required values are tenant, user, agent, delegation and task. The configured `access_broker.tenant_id` is the console management boundary and must match request identities. Register the agent and create a matching delegation in the console before sending traffic. High-risk requests can create an approval; the caller must obtain a new JWT carrying the returned `approval_id` (or otherwise place that value in the configured approval claim) and repeat the exact request once. Do not let an untrusted caller mint or rewrite these claims.

## Integration acceptance checklist

Before declaring a client/service integration supported, verify: configurable endpoint and headers; successful service authentication; mapped MCP initialization/discovery (if used); an allowed operation; a denied operation with no destination side effect; request/response PII behavior; target 401; and inspector-path failure with no bypass. Check the client does not silently fall back to a direct URL. A healthy container is not an acceptance test.

## Policies, networking and limits

The UI edits action/PII policies and passwords. Destinations, transport/auth modes, body limits and mappings are startup configuration in `deployment.yaml`. New requests use the applied policy; in-flight requests retain their original snapshot. Keys such as `1:notes.read` identify a route index and tool; do not reorder routes casually.

Default listeners are host loopback only: console 18080, gateway 18084. Envoy 18082 and gRPC 18081 have **no host-published ports**. The inspection network is internal; the app also has an edge network for published listeners, while Envoy uses a separate egress network. The app has outbound connectivity but its forwarding implementation only sends to Envoy. No Docker socket or host network privileges are mounted. The local volumes contain credentials, policies and audit state; protect host access and backups.

For remote use, front both public listeners with a trusted TLS reverse proxy, set the exact `console_origin`, and expose only the intended TLS endpoint. `TD_BIND_ADDRESS`, `TD_CONSOLE_PORT`, `TD_GATEWAY_PORT` change published listeners; they do not enable TLS. An HTTP management origin does not get secure cookies. Do not expose plaintext service credentials to an untrusted network. Prevent clients from bypassing the gateway using network controls appropriate to your environment.

This profile buffers bodies up to 1 MiB, uses a five-second Envoy request/route budget and bounded inspection workers. It rejects unsupported streaming/session behavior; it is not for large uploads or indefinite streams. Mirror does not modify content or enforce action/PII verdicts, but adapter authentication, route admission and transport failure boundaries still apply. Test inline failure behavior before production use.

## Operations and data lifecycle

```bash
docker compose ps
docker compose logs --tail=100 app envoy
docker compose restart
# Stop without deleting state:
docker compose down
```

A healthy app or reachable listener is not proof that target authentication or inspection works. Always use a known request and inspect its decision. No customer request payloads or credentials are intentionally written to console evidence. SQLite and replay state survive container replacement. Local audit records are mutable; this is not a central immutable audit service. Monitor disk usage; this preview has no automated retention scheduler.

Backup: stop the stack, snapshot **both named volumes** (`<project>_state`, `<project>_generated`) and keep the exact source revision and configuration/secret mounts securely. Restore to an isolated instance and test sign-in plus one allow/block request. Do not copy a running SQLite file as your only backup. `docker compose down -v` destroys passwords, keys, policies and audit records.

Upgrade: back up first, record the previous image ID/source revision, build the selected version, render configuration and recreate the stack. Review any policy migration before startup. Rollback restores the previous source/image **and its matching stopped-state backup**; restoring only an older image is not a database compatibility guarantee.

Mapping migration: this preview deliberately refuses startup when saved policy keys no longer match route/tool mappings. Stop the stack and back up first. Use the `policy-reset` command to explicitly discard only saved policy settings and let the new YAML seed them on startup; accounts, keys and events remain. Existing rule changes will be lost, so export/review your old policy first.

```bash
docker compose run --rm app policy-reset
docker compose run --rm app render
docker compose up -d --force-recreate
```

Multi-node HA, automatic credential rotation, managed Cloud operations and universal MCP compatibility are outside this package. Per-agent identity is available through local agent credentials or explicit verified JWT claim mapping. External issuer integration still requires customer validation.

## AISG autonomous JWT configuration

Set `gateway_auth.identity_mode: agent` with `identity_claims` mapping only trusted tenant/agent values (for example tenant_id to `tid`, agent_id to `azp` for an explicitly registered workload). Register that exact value in the Agent Registry, enable autonomous access, and assign action/resource/tool scopes. No user, task or delegation is synthesized. The default remains `delegated`. Shared client IDs identify the application, not distinct agent instances.

The local `agent_key` profile uses an opaque Bearer credential, not OAuth discovery or an OAuth issuer. Clients must support static Bearer configuration. For OAuth clients use the external JWT profile. Destination authentication and target permissions remain independent.

Local keys are hashed in `/state/agent-credentials.sqlite`. The console issues, rotates, revokes and lists metadata under `/demo-api/agents/{agent_id}/credentials`; mutations require an administrator session and CSRF protection. Never expose this console API as a client authentication API. Rotation revokes the selected key immediately. An agent may hold multiple keys; revoke each or disable the agent to block all.

## 0.44 · Buffered SSE

[Buffered SSE latency and rollout fit](latency.md)

The gateway collects and inspects the complete supported response before delivering content. Client first-content latency includes collection and inspection, not just scanner time. This suits workflows that can wait for a complete result; interactive chat must be tested against an explicit latency budget.
