# One open-source product

> **AISG:** [Connect, identify, control, verify](aisg.md). Gateway access uses a deployment key or verified JWT. Local agent_key mode identifies a registered agent without an external IAM. JWT identity_mode: agent uses verified tenant/agent claims; delegated mode additionally requires user, task and delegation. Existing agents require delegation by default.

[English](../en/editions.md) · [한국어](../ko/editions.md) · [简体中文](../zh-CN/editions.md) · [日本語](../ja/editions.md) · [Español](../es/editions.md) · [Français](../fr/editions.md)

TrapDefense 0.44 has one MIT-licensed codebase. Runtime inspection and Agent Access Broker capabilities ship together in this repository. No private Python distribution, provider entry point, license key, or edition switch is required.

## What is shipped

| Boundary | Status | Evidence and limit |
|---|---|---|
| Runtime Gateway and console | **Open Source Preview** | Public source, CI, synthetic Envoy path, HTTP/MCP policy, PII/secret controls, and local operations UI. Production routing and capacity remain deployment-specific. |
| Built-in Agent Access Broker | **Experimental** | Public registry, delegation, strict authorization, tenant isolation, file transactions, and request-bound one-time approval. Real customer IdP/policy and multi-node validation remain required. |
| Docker self-hosting | **Preview** | Source-built adapter, Envoy, inspector, console, gateway authentication, and separate target credentials. One fixed destination origin per installation. |
| Managed cloud, fleet, multi-node HA, immutable external audit | **Planned** | These services are not shipped and are not represented as currently available. |

Gateway-only deployments use local inspection policy and trusted-source verification. Broker-enabled deployments add verified JWT identity mapping, agent registry, delegation, resource/action authorization, and approval. Both modes use the same open-source package.

## Commercial direction

Future paid offerings can operate the same open-source runtime as a managed service and add fleet lifecycle, multi-node HA, durable external audit, customer connectors, policy onboarding, SLA, and support. This is a service and operations boundary, not a source-code feature gate.

## Security statement

The built-in file store is safe for same-host POSIX processes with atomic replacement and file locking. It is not a distributed database and must not be placed on NFS/SMB for multi-host HA. Local JSON and SQLite evidence is mutable. Broker decision tokens are scoped evidence and not downstream OAuth access tokens.

Synthetic tests establish protocol behavior, not production certification for Entra, Okta, Keycloak, Conditional Access, customer MCP authentication, TLS routing, or capacity.

[Docker 0.44](self-hosting.md) · [Architecture](architecture.md) · [Security](security.md) · [Gateway compatibility](gateway-compatibility.md)
