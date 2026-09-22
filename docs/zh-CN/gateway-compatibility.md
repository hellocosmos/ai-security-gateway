# 网关客户端兼容性 — 0.44

> [模型提供商连接](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [连接、识别、控制、验证](aisg.md). 网关使用部署密钥或已验证 JWT。agent_key 无需外部 IAM 即可识别注册代理。JWT identity_mode: agent 使用已验证的租户和代理声明；delegated 还要求用户、任务和委托。现有代理默认需要委托。

[English](../en/gateway-compatibility.md) · [한국어](../ko/gateway-compatibility.md) · [简体中文](../zh-CN/gateway-compatibility.md) · [日本語](../ja/gateway-compatibility.md) · [Español](../es/gateway-compatibility.md) · [Français](../fr/gateway-compatibility.md)

客户端必须能把远程 HTTP/MCP URL 改为 TrapDefense，并发送连接密钥请求头或 OAuth Bearer JWT。客户端到 TrapDefense 的认证与 TrapDefense 到目标的认证彼此独立。

| 路径 | 0.42 证据 |
|---|---|
| 通用 JSON HTTP | 已完成 HTTPX 合成集成验证 |
| 官方 Python MCP SDK 1.30.0 | 已完成 MCP `2025-11-25` 初始化、通知和工具列表的合成集成验证 |
| 类 Entra OAuth | 合成验证 `scp`、`tid`、`oid`、`azp` 以及 discovery、DCR、PKCE 和 resource binding；未验证真实 Entra tenant |
| 类 Okta OAuth | 通过完整合成流程验证数组型 `scp` 和 `cid`；未验证真实 Okta server |
| 类 Keycloak / 真实本地 Keycloak | 除完整合成流程外，还验证了固定 digest 的官方 Keycloak 26.7.3 容器签发的真实本地 token、discovery 和 JWKS |
| VS Code 1.135 远程 MCP | 已在实际安装产品中确认 `Running`、发现 1 个工具、三项 MCP receipt 以及 `2025-11-25` 初始化请求 |
| 有状态 MCP、长连接 SSE、WebSocket、stdio | 不支持；session header 与 upstream SSE 会 fail closed |
| 多节点 HA | 不支持；当前为单 gateway，使用本地 SQLite、replay 与 audit state |

`gateway_auth` 使用 `client_key` 或 `jwt`。JWT 模式下 TrapDefense 是 OAuth Resource Server，并发布 RFC 9728 metadata 与 `WWW-Authenticate`。`scope`/`scp` 可以是空格分隔字符串或字符串数组；可选的 `authorized_parties` 会限制 `azp`、`appid` 或 `cid`。0.42 不把 Entra `roles` app role 当作 scope。

`target_auth` 支持 `none`、`passthrough_bearer`、`static_bearer` 和 `static_api_key`。Gateway JWT 不会转发给目标。登录、token 签发、refresh 和 OBO 由外部 IdP 或独立 credential provider 负责。

正式批准集成前，请验证 URL 替换、两侧认证、MCP 初始化/发现、允许与拒绝、目标副作用、PII/secret、目标 401、检查链路故障以及是否回退到直连 URL。复现命令、配置和来源见[英文指南](../en/gateway-compatibility.md)。


当前证据包括真实 OpenAI 到合成 MCP 的流程、官方供应商 SDK 合成测试、本地真实 MCP/Keycloak 及 VS Code 初始化/发现。模型 SSE 完整缓冲；有状态 MCP、客户 IAM 策略、跨主机 HA 和生产容量未获认证。参见 [0.42 验证与限制](agent-workflow.md)。
