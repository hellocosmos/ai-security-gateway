# Changelog

## 0.44 — Buffered SSE latency evidence

- Add bounded process-local gateway and inspector timing distributions to the six-language operations console.
- Add a reproducible Docker/Envoy direct-versus-gateway SSE benchmark, overload and fail-closed boundary checks.
- Document first-content latency, response collection, inspection queues and workload suitability without production capacity claims.
- Preserve whole-response buffering and existing authorization/policy behavior.

## 0.43 — Operator workspace

- Connection profiles, validation, staged configuration, protected destination secrets and saved revision recovery in the Docker console.
- Explicit stopped-stack activation; persistent active configuration and policy snapshots. No Docker socket or live reload.
- Isolated local-policy previews and inspection-listener/request-outcome diagnostics without bypassing egress isolation.
- First-success guidance and operator documentation in six languages.
- Real customer MCP/account qualification remains separate from synthetic Docker verification.

## 0.42 — Two-gateway agent workflow

- Align current installation, identity, compatibility and provider guides across six languages; check documentation links and current guide titles in CI. Historical migration versions and labeled screenshots retain their provenance.

- Add a reproducible Docker example joining an official OpenAI SDK tool loop to an official MCP client through independent fixed-origin gateways.
- Verify Agent A allow, Agent B scope denial, local deletion policy, request/response PII redaction, used-key revocation and seeded expired credentials against actual target receipts and sanitized decision records.
- Scripted synthetic TLS model by default; explicit optional live OpenAI mode with a private key file, request/token limits, no retries and no synthetic fallback. Live OpenAI gpt-4.1-mini passed all three scenarios on 2026-09-18 with a synthetic MCP target.
- Fix live-model response false positives: discard native LLM response cookies before forwarding and recognize bounded native Chat Completions and OpenAI Responses creation timestamps, including supported SSE paths; preserve nested business-data inspection.
- Add six-language workflow guides. Existing provider, streaming, IAM and HA boundaries remain unchanged.
- Add a deterministic Docker agent-workflow CI job and document local MCP, same-host recovery, buffered-stream and bounded overload evidence. Cross-host HA and other live provider accounts remain unqualified.

## 0.41 — Native model provider connections

- Add fixed-origin OpenAI, Anthropic, Gemini and OpenRouter profiles with exact model allowlists.
- Accept native SDK credential slots for gateway connection keys or individual agent keys; replace them with separately stored provider credentials.
- Support native text/function calls and bounded, fully inspected SSE delivery. Add Gemini event reconstruction and escaped JSON argument inspection.
- Preserve HTTP/MCP defaults; expose provider/model/buffering limits in six-language console guidance.
- Add official Python SDK synthetic compatibility tests. Streaming is buffered, not real-time; no live-provider certification or package release is implied.


## 0.40 — AI Security Gateway

- Explicit AISG positioning and six-language connection guides.
- Local expiring agent credentials with hashed storage, atomic rotation, revocation and live registry checks.
- Opt-in autonomous agent authorization with action/tool/resource allowlists; existing delegated mode remains the default.
- Mode-bound one-time approvals and side-effect-free mirror evaluation.
- Console credential lifecycle and agent enable/disable controls.
- Synthetic Docker agent-key profile; bounded JSON HTTP/MCP transport limits remain unchanged.


All notable changes to TrapDefense AI Firewall are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Source releases currently run from `0.31` through `0.39`.

## [Unreleased]

## [0.39] - 2026-09-17

### One open-source product

- Ship the Runtime Gateway, Agent Registry, delegation, Access Broker, request-bound human approval, audit and operator console in one MIT-licensed repository.
- Remove the Community/Enterprise edition switch and private `trapdefense.authorizers` provider dependency; `access_broker_enabled` selects the built-in broker.
- Rename the Python distribution and Docker image to `trapdefense-ai-firewall`.

### Identity and operations

- Map an explicit allowlist of verified JWT claims to tenant, user, agent, delegation, task, instance and approval identity fields.
- Fail startup when broker mode lacks JWT authentication, identity mapping or a configured tenant.
- Operate agents, delegations and approvals from the console; the synthetic deployment scenario uses the real broker and proves one-time approval consumption.
- Support the transactional file-backed broker with the same-host inspector pool while retaining the multi-host HA limitation.

### Boundaries

- Access Broker is Experimental pending production IdP, customer policy, routing, HA and capacity validation.
- Managed cloud, fleet operations and immutable external audit remain planned services rather than shipped features.

## [0.38] - 2026-09-17

### Compatibility lab

- Exercise Entra-, Okta- and Keycloak-shaped OAuth claim dialects through the pinned official MCP SDK, including authorization-server discovery, dynamic client registration, authorization code with PKCE, RFC 8707 resource binding and MCP `2025-11-25` initialization/tool discovery.
- Accept OAuth scope claims as either a space-delimited string or a string array, and optionally restrict caller applications through common `azp`, `appid` or `cid` claims.
- Validate a real token from an unmodified, digest-pinned Keycloak 26.7.3 container using its discovery and JWKS endpoints; consume the gateway token without forwarding it to the target.
- Verify the installed VS Code 1.135 client reports the server running, discovers one tool and completes `initialize`, `notifications/initialized` and `tools/list` with a `2025-11-25` initialization request.
- Return `405 Method Not Allowed` with `Allow: POST` when a Streamable HTTP client probes GET or DELETE on a stateless MCP route, avoiding a false OAuth fallback while preserving the unsupported session boundary.

### Boundaries

- Provider-shaped tests use synthetic authorization-server behavior and do not prove a real Entra or Okta tenant, Conditional Access, revocation, TLS or production claims policy.
- Stateful MCP session headers, upstream SSE, WebSocket, stdio and multi-node HA remain unsupported and fail closed in this profile.

## [0.37] - 2026-09-17

### Gateway interface compatibility

- Separate `gateway_auth` and `target_auth` configuration while retaining the 0.36 client-key and legacy configuration path.
- Add external-issuer RS256 JWT validation for issuer, audience, time, subject and required scopes, plus RFC 9728 Protected Resource Metadata and gateway-owned OAuth challenges.
- Consume gateway JWTs before forwarding and inject an independent fixed-target Bearer or API-key credential; reject JWT plus Bearer passthrough at configuration time.
- Verify actual HTTP JWKS retrieval with ephemeral synthetic RSA material and complete the pinned official Python MCP SDK 1.30.0 initialize/notification/tool-discovery flow through the gateway.
- Publish a six-language compatibility matrix and current VS Code configuration example, clearly separating source-checked configuration, synthetic integration evidence and unverified real IdP/client operation.

### Boundaries

- Community remains an OAuth resource server, not an authorization server, token vault, OBO broker, Agent IAM registry or general stateful streaming proxy.
- Real Entra/Okta/Keycloak tenants, Conditional Access, revocation, VS Code execution, stateful MCP, long-lived SSE and customer routing remain deployment-specific validation.

## [0.36] - 2026-09-17

### Docker self-hosting preview

- Source-built Compose package: authenticated signing adapter, private Envoy/inspector and persistent operations console. No host Docker socket.
- Explicit fixed-destination JSON HTTP/stateless JSON MCP contract; separate deployment key and destination Bearer/API Key credentials, optional static bearer file.
- Initial administrator password, persistent keys/policies/events, explicit mapping reset, HTTPS upstream validation and fail-closed forwarding.
- Deployment-aware UI and six-language installation/integration guides. Existing synthetic demo remains available separately.
- No claim of Cloud availability, universal OAuth/MCP compatibility, customer IAM validation, long-lived SSE support or HA.

## [0.35] - 2026-09-17

### Added

- Optional real MCP pilot using the pinned official Python SDK: initialization, discovery and persisted document tool operations through the existing Envoy/Community inspector.
- Separate local signing adapter with fixed destination, private key, fresh attestations, reserved-context removal and bounded forwarding; no agent SDK or production network-isolation claim.
- Deterministic request/response PII and secret checks, denied deletion with downstream state verification, unknown/unsigned calls and inspector-outage blocking.
- Bounded actual local LLM tool loop with schema validation, explicit model endpoint, no scripted fallback, no identical-call replay and sanitized model/protocol evidence.
- Six-language guides, direct-versus-proxy sequential latency measurements and an opt-in CI regression.

### Documentation

- Clarify supported HTTP/MCP deployment paths, existing authentication, self-hosted availability and planned Docker packaging / managed Cloud across six languages.

### Limits

- A semantic malicious instruction outside the current signatures passes unchanged. The pilot records this known detection miss separately from policy enforcement.
- Model refusal, incomplete tasks and unexercised cases are distinguished from firewall detection. Response blocking cannot undo an already-executed tool action.
- Stateless Streamable HTTP JSON and finite synthetic documents only; no customer MCP/OAuth, production sizing, HA or language migration claim.


## [0.34] - 2026-09-16

### Operations

- Same-host 1/2/4 inspector supervision, active Envoy health checks and bounded process recovery.
- Console worker status and administrator apply/start/stop controls, with shared versioned policies and sanitized events.
- New streams read the committed policy; in-flight streams retain the request policy snapshot.
- Opt-in Linux systemd user-service installer and removal commands. Host boot/linger validation remains deployment-specific.
- Six-language operation guides. Cross-server HA remains unimplemented.

### Verified

- Ubuntu 26.04 lab installation: 369 unit tests, 10 console tests and 6 real Envoy/pool tests passed; 31 opt-in tests were skipped in the default suite.
- Real host reboot with linger: automatic startup before SSH login, two healthy inspectors, persisted policy/events and synthetic allow/block/redaction traffic.
- Browser verification of inspector controls and English/Korean rendering; desktop/mobile landing operations layout checked.
- Runtime pool tests now use the native Docker context on Linux instead of requiring Docker Desktop.

### Performance and security

- Equivalent ASCII candidate prefilters for fixed PII/signature patterns, native control-character cleanup and indexed nonce expiry.
- Shared local replay state across workers; no automatic tool-call retry. Exhausted worker recovery stops the pool.
- Process scaling changes briefly interrupt the proxy; failed changes attempt rollback, with unavailable inspection failing closed.


### Added

- A bounded `trapdefense-benchmark` command for repeatable sequential measurements through the local Envoy, gRPC inspector and synthetic destination path.
- Community Preview maturity labels, five-minute evaluation success criteria and explicit shipped/private/roadmap edition status.

## [0.33] - 2026-09-16

### Added

- Deterministic PII policy overrides for HTTP/MCP routes and mapped actions or MCP tools, with tool/action → route → global precedence.
- Request-selected PII policy propagation into supported JSON, text and complete buffered SSE responses.
- Console controls for per-tool inherit, redact or block behavior and sanitized evidence of the selected policy scope.

### Security

- Mirror keeps original request and response bytes unchanged while complete detections retain explicit `would_redact` or `would_block` assessments.
- Incomplete capture, unsupported inspection and transport failures remain `unknown`; policy evidence never stores inspected content.
- Existing configurations inherit the global PII action unless an explicit route or tool override is present.

### Verified

- Synthetic tool, route and global precedence tests for request and response inspection.
- Six matching UI dictionaries and localized console/security guidance.
- Community proxy integration covers a tool-specific block policy in Mirror mode without enforcement or request mutation.

## [0.32] - 2026-09-16

### Added

- Bounded offline detection for recognized AWS, GitHub, GCP, Slack, Stripe and OpenAI token forms.
- Structural signed-JWT validation, Azure Storage SAS query detection and high-entropy credential checks for sensitive JSON fields.
- Secret inspection across supported request bodies, responses, headers and reassembled SSE streams.
- A six-language `Block leaked credential` console scenario that traverses the installed Envoy path.

### Security

- Recognized credentials fail closed with the stable `secret_detected` reason and captured values are never copied into verdict evidence or audit records.
- Request authorization, cookie and API-key headers remain pass-through only on the signed, explicitly mapped destination path; response headers are inspected.
- Malformed JWT-like strings, ordinary `sig` query parameters and documented placeholders are excluded to reduce obvious false positives.

### Verified

- Synthetic provider-token, JWT, Azure SAS, sensitive-field, request, response, SSE split-stream, credential-header and sanitized-evidence tests.
- Existing Community request, response, PII, protocol, console and proxy integration suites.

## [0.31] - 2026-09-16

### Added

- Offline PII profiles for English, Korean, Simplified Chinese, Japanese, Spanish and French.
- Checksum-validated Chinese GB 11643 resident IDs, Japanese Individual Numbers and French NIR social security numbers.
- Presidio Spanish NIF, NIE and passport recognition.
- Region-aware phone recognition for Chinese, Japanese, Spanish and French inputs.

### Security

- National identifier patterns reject invalid dates or check digits instead of accepting format-only matches.
- All six language profiles run for every supported payload, so the configured UI language does not change enforcement.
- Inspection remains deterministic and offline. Names, locations, addresses, images, OCR and general NER are explicitly outside this release.

### Verified

- Locale-specific positive, invalid-checksum, redaction, timeout and no-network tests.
- Existing request, response, SSE and fail-closed inspection suites.

## [0.3.0] - 2026-09-16

### Added

- Self-hosted Community AI Firewall with Envoy ExtProc request and response inspection.
- A local operations console for dashboard, event, policy, connection, audit and settings workflows.
- Explicit HTTP and MCP action mappings, local allow/block rules, PII block or redaction, trusted-hop signatures and replay protection.
- Sanitized local decision evidence and synthetic HTTP scenarios that traverse the proxy path.
- Single-tenant Microsoft Entra ID console SSO with Administrator and Viewer app roles, plus a protocol-realistic synthetic Entra flow for local evaluation.
- English, Korean, Simplified Chinese, Japanese, Spanish and French console dictionaries and guides.

### Security

- Inline inspection fails closed when complete policy evaluation cannot finish.
- Console writes require same-origin requests and a CSRF header, and local login attempts are rate limited.
- Community source verification remains distinct from Enterprise agent identity verification and delegated authorization.

### Verified

- Community tests run on Python 3.11 and 3.12 in GitHub Actions.
- Console type checks and production build run on Node.js 22 in GitHub Actions.
- Linux CI runs the Envoy to gRPC inspector to synthetic HTTP destination integration test.

### Known boundaries

- This is a source installation; no PyPI package is implied.
- The included screens and scenarios use synthetic data.
- A real Entra tenant, customer TLS path, enforced production routing, high availability and performance are not certified by this release.
- Local audit storage is mutable, and content detection can produce false positives or false negatives.
- Enterprise Access Broker, approvals and delegated authorization are distributed separately.

[0.39]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.39
[0.38]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.38
[0.37]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.37
[0.36]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.36
[0.35]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.35
[0.34]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.34
[0.33]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.33
[0.32]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.32
[0.31]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.31
[0.3.0]: https://github.com/hellocosmos/ai-security-gateway/releases/tag/v0.3.0
