# Console installation and operation

> **0.44:** [Operator workspace (0.44)](operator-workspace.md)


> **AISG:** [Connect, identify, control, verify](aisg.md). Gateway access uses a deployment key or verified JWT. Local agent_key mode identifies a registered agent without an external IAM. JWT identity_mode: agent uses verified tenant/agent claims; delegated mode additionally requires user, task and delegation. Existing agents require delegation by default.

> Docker 0.44: [Self-hosting / integration guide](self-hosting.md) · [Gateway client compatibility](gateway-compatibility.md). This page describes the separate source-based synthetic demo.

[English](../en/console.md) · [한국어](../ko/console.md) · [简体中文](../zh-CN/console.md) · [日本語](../ja/console.md) · [Español](../es/console.md) · [Français](../fr/console.md)

The console can use single-tenant Microsoft Entra ID SSO with Administrator and Viewer roles. Console operator authentication is separate from agent authorization. The built-in Access Broker is available in the same open-source package. [Identity boundaries](identity.md).

## Install and start

Requirements: Python 3.11+, Node.js 22.12+ (or 24), npm, and a running local Docker Engine/Desktop. Install from this repository; no SDK, private runtime package or model API is required. Scripts use an existing `uv` installation when available, otherwise Python venv/pip. Run without sudo and keep Docker local.

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway
./scripts/install-console.sh
./scripts/run-console.sh
```

Open [http://127.0.0.1:5176](http://127.0.0.1:5176). The first account is **admin / 1234** . Change it in **Settings → Administrator password** ; changing it revokes all sessions. The console binds to loopback and is a local evaluation installation, not an Internet-facing appliance. A port conflict stops startup without killing existing services. Stop with Ctrl+C; only this installation's labeled Envoy container is removed.

## Language

Use the language selector on the sign-in page or top bar. English is the default; Korean, Simplified Chinese, Japanese, Spanish and French are included. Selection persists in this browser and does not sign you out. Documentation opens in the selected language. Tool names, rule codes, identifiers and user-entered content remain unchanged. UI translation does not expand PII-language coverage.

## Actual traffic path

```text
Browser -> management API/UI :5176
                 -> signed synthetic sender -> Envoy :18082 -> HTTP destination :18090
                                                 <-> gRPC inspector :18101–18104
                 <- response inspection <- decision + receipt <- UI
```

The sender simulates a trusted forwarding hop and signs exact synthetic requests; it is not a TLS decryptor or identity provider. Envoy is real, and the no-op destination is a separate HTTP listener. The demo seeds the real built-in broker with synthetic identities and demonstrates request-bound approval without executing an external business action.

## Pages and a first walkthrough

1. **Dashboard:** run business-read, PII redaction, leaked-credential blocking, protected deletion, injection, external transfer and response PII scenarios. Data is produced by real requests, not prefilled verdicts.
2. **Traffic / Events:** filter decisions and open details. Check HTTP status, destination receipt, masking and policy version. CSV exports contain sanitized metadata.
3. **Policies:** change `notes.read` to block, validate, apply, and rerun. Restore allow when finished. Updates apply to new streams; in-flight streams retain their policy snapshot.
4. **Connections / System:** inspect component readiness and the actual path. ** Audit:** review sign-in, policy and network changes.
5. **Settings:** inspect host interfaces and change the proxy listener port, timeout or body limit. Validate invokes Envoy's validator. Apply briefly restarts the owned container, checks the new listener and restores the previous configuration on failure.

## Route and tool PII policy

The global PII action is the default. An HTTP/MCP route can override it, and a mapped action or MCP tool can override the route. The exact precedence is **tool/action → route → global**; omitted values inherit. The selected action and scope are stored in sanitized decision evidence and reused for the corresponding response.

Use **Policies → PII override** to set each demo tool to inherit, redact or block. In Mirror mode, the original request and response are not changed and the UI reports **Would allow**, **Would redact** or **Would block**. `unknown` remains reserved for incomplete capture or inspection failure; Mirror results are evaluation evidence, not production enforcement proof.

## Network settings and NICs

| Setting | Default / meaning |
|---|---|
| Deployment | Explicit L7, single loopback interface |
| Management API/UI | `127.0.0.1:5176` |
| Proxy ingress | `127.0.0.1:18082`, configurable unprivileged port |
| Inspector | `127.0.0.1:18101–18104`, gRPC ExtProc |
| Destination | `127.0.0.1:18090`, synthetic HTTP only |
| Request timeout | 5 seconds; configurable 2–30 |
| Body limit | 1 MiB; configurable 1 KiB–1 MiB |
| Interfaces | Live host names, addresses, link state, MTU and installation role |

Interface count is not physical NIC count: loopback, bridges and tunnels are included. The installed profile uses loopback; it does not configure physical one-/two-NIC routing, transparent bridging, OS IP/routes or physical egress pinning. Arbitrary production destinations are not exposed by this form. On macOS, Docker Desktop forwards to host services. Linux uses host networking for loopback reachability. Envoy 1.39.1 is pinned by a multi-architecture digest (amd64/arm64).

## Inspection and failure modes

**Inline** allows, blocks or masks. Unmapped/unsigned requests are denied. An inspector communication failure fails closed. ** Mirror in this console** observes the same synchronous proxy path without modifying content or consuming approvals; communication failures still block. The separate mirror collector in the lower-level inspector receives copies and cannot affect the original. Neither is unbounded streaming inspection. No direct-engine fallback is used when the proxy fails.

## Persistence and troubleshooting

`.runtime-state/console` stores account hashes, session hashes, policy, network settings and sanitized SQLite events. Set `TD_CONSOLE_STATE` to a different private directory if needed. Back it up while stopped; changing the path starts a separate installation. It is excluded from Git. The signing key is ephemeral within this demo; external trusted hops are not provisioned. Destination receipt counters reset on process restart; saved transaction evidence remains. Audit is local and editable, not immutable.

If startup fails, check Docker availability and ports 5176/18101–18104/18111–18114/18090 plus the configured proxy port. Do not stop unrelated services automatically. Missing inspection evidence is an error, not success. Runtime latency includes local/container effects and is not a production benchmark. Real TLS equipment, IAM, forced routing, HA and production hardening require separate validation.

## Verify and maintain translations

```bash
.venv/bin/python -m pytest -q
npm run check --prefix console
npm run build --prefix console
# Stop the running console before this Docker test.
TD_CONSOLE_E2E=1 .venv/bin/python -m pytest tests/test_console.py -q
```

Without `TD_CONSOLE_E2E=1`, Docker tests are skipped. Locale checks require identical keys and placeholders across all six dictionaries and English application source. Update English keys and all locale JSON files together; keep stable API codes unchanged. English documentation is the reference when translations differ. See [architecture](architecture.md), [editions](editions.md), [migration](migration.md) and [security](security.md).


## Same-host operations

[1 / 2 / 4 inspectors · Linux service](operations.md)
