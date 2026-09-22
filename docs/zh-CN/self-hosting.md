# Docker 自托管 — 0.44 Open Source Preview

> **0.44:** [运维工作区（0.44）](operator-workspace.md)


> [模型提供商连接](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [连接、识别、控制、验证](aisg.md). 网关使用部署密钥或已验证 JWT。agent_key 无需外部 IAM 即可识别注册代理。JWT identity_mode: agent 使用已验证的租户和代理声明；delegated 还要求用户、任务和委托。现有代理默认需要委托。

[English](../en/self-hosting.md) · [한국어](../ko/self-hosting.md) · [简体中文](../zh-CN/self-hosting.md) · [日本語](../ja/self-hosting.md) · [Español](../es/self-hosting.md) · [Français](../fr/self-hosting.md)

## 选择 0.44 起点

- **模型 API：**使用[供应商配置](providers.md)连接 OpenAI、Anthropic、Gemini 或 OpenRouter。修改 SDK base URL，供应商密钥保存在网关。
- **HTTP / MCP 工具：**从下方 Docker 示例开始，再将合成目标替换为显式映射的服务。
- **端到端验证：**运行[双代理模型 → MCP → 模型示例](agent-workflow.md)。默认无需付费密钥；指南区分真实 OpenAI 证据、合成测试和测量限制。

网关支持 `client_key`、`agent_key` 和外部 `jwt`。本地 Agent Registry 和 agent_key 权限控制可选，不能替代目标认证。每个部署仅有一个固定目标，模型与单独执行的工具需要各自路由。模型 SSE 完整缓冲并检查后才交付，不是实时 token 流。

0.44 提供适配器、Envoy、检查器、管理界面以及相互独立的网关/目标认证。镜像从源码本地构建。TrapDefense Cloud 仍在规划中，尚未开放注册。

客户端必须能修改 MCP/API URL，并使用 `X-TD-Client-Key` 或 OAuth Bearer JWT。每个部署只有一个固定目标，并显式映射路由和工具。证据见[兼容性表](gateway-compatibility.md)。

| 类型 | 支持范围 |
|---|---|
| HTTP API | JSON、精确 method/path、最大 1 MiB、有界响应 |
| MCP | 无状态 JSON POST、显式映射的控制方法和工具 |
| 网关认证 | 连接密钥，或外部 IdP 的 RS256 JWT（issuer/audience/scope 与 RFC 9728 元数据） |
| 目标认证 | none、旧式 Bearer 透传、文件支持的固定 Bearer/API Key |
| 不支持 | OAuth 签发、登录代理、DCR、OBO、Cookie/会话、长连接 SSE、WebSocket、stdio、封闭 SaaS 内部调用 |

管理员密码用于控制台登录。连接密钥或 JWT 用于访问 TrapDefense。JWT 针对配置的网关 audience 验证且不会传给目标；目标服务使用独立凭据检查权限。连接密钥或 JWT 不会自动注册代理。代理注册与权限由可选 Access Broker 单独管理；OAuth 签发由外部 IdP 负责。

## Docker

需要 Git 和 Docker Compose v2。init 要求设置至少 12 个字符的管理员密码，没有默认密码。示例配置指向合成目标，不代表真实服务集成。

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
docker compose run --rm app client-key
```

在 `http://localhost:18080` 以 admin 登录。使用 client-key 命令读取连接密钥，并存入客户端的机密请求头配置。网关为 `http://localhost:18084`；合成目标令牌为 `Bearer synthetic-target-token`。

连接真实服务时修改 deployment.yaml 中的 upstream、authority、路径、工具和 resource。`gateway_auth` 使用 `client_key`、`agent_key` 或 `jwt`；`target_auth` 使用 `none`、`passthrough_bearer`、`static_bearer` 或 `static_api_key`。JWT 不能与 passthrough 组合。固定凭据必须使用 UID 10001 可读的 0600 文件，冲突输入会被拒绝。

UI 管理策略和密码。变更映射时，先备份，再运行 policy-reset、render 并重建服务。此操作仅重置已保存策略，保留账户、密钥和事件。新请求使用新策略。

默认端口只绑定回环地址。远程访问需要 TLS 反向代理和准确的 console_origin。检查器和 Envoy 不公开主机端口。客户需通过网络控制防止绕过。

重启保留命名卷中的状态。停止后备份两个卷及配置。down -v 会删除数据；回滚需旧镜像及对应备份。监听器健康不能证明认证或检查成功，请验证允许、阻止及目标副作用。长连接、HA 和真实客户 IAM 需单独验证。

[兼容性与 VS Code](gateway-compatibility.md) · [Detailed examples, backup and migration (English)](../en/self-hosting.md)

## 启用内置 Access Broker

以下说明 **delegated JWT 模式**。本地 agent_key 和自主 agent 模式请参见 [AISG 指南](aisg.md)。

使用 `gateway_auth.mode: jwt`，并在 `identity_claims` 中明确 tenant、user、agent、delegation 与 task claim 名称。随后设置 `access_broker.enabled: true` 和唯一的 `access_broker.tenant_id`。必须先在控制台注册同一 tenant 的 agent 与 delegation。缺少必需 claim 或 tenant 不匹配会在转发前拒绝。完整 YAML 请以[英文基准文档](../en/self-hosting.md)为准。本地 file store 仅适合同主机，不是 multi-node HA。

## 0.44 · Buffered SSE

[Buffered SSE 延迟与部署适用性](latency.md)

网关收集并检查完整的受支持响应后才交付内容。首内容延迟包括收集与检查，不只是扫描时间。适合能等待完整结果的任务；交互聊天需按明确的延迟预算评估。
