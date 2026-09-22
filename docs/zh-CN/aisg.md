# TrapDefense — AI Security Gateway (0.44)

> [模型提供商连接](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

[en](../en/aisg.md) · [ko](../ko/aisg.md) · [zh-CN](../zh-CN/aisg.md) · [ja](../ja/aisg.md) · [es](../es/aisg.md) · [fr](../fr/aisg.md)

通过明确的安全边界连接受支持的 HTTP API 和远程 MCP 服务器。需要逐代理控制时添加代理身份。

## 连接、识别、控制、验证

启动 Docker 合成环境，在 Access Broker 注册代理，为选定工具启用自主访问并签发凭据。修改客户端 URL，在 Authorization 头中发送凭据。分别测试允许与拒绝的调用并检查决策记录。

## 选择身份模式

网关使用部署密钥或已验证 JWT。agent_key 无需外部 IAM 即可识别注册代理。JWT identity_mode: agent 使用已验证的租户和代理声明；delegated 还要求用户、任务和委托。现有代理默认需要委托。

## 凭据生命周期

本地凭据可在1小时、24小时或最多30天后过期。仅存储哈希，新凭据仅显示一次。轮换立即撤销旧密钥。撤销凭据或禁用代理会阻止后续认证。网关凭据与目标服务凭据分开。

## 兼容性与限制

每个安装仅有一个固定目标，支持明确映射的 HTTP JSON 和无状态 MCP JSON POST。不支持 SSE、状态会话、stdio、WebSocket 或 SaaS 内部调用。仅修改模型 API base_url 不会路由单独执行的工具。请配置各工具端点并通过客户网络策略阻止绕过。

## 审批

自主访问检查工具、资源和操作权限。高风险操作仍需有期限且绑定请求的审批。审核后，以本地密钥和 X-TD-Approval-ID 重试相同请求；审批仅消费一次。Mirror 不创建或消费审批。

## 验证范围

本地合成验证不代表生产 IdP、客户路由、HA 或容量认证。Access Broker 仍为实验功能。目前无托管云注册服务。

## 快速开始

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
