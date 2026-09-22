# TrapDefense — Open-source AI Security Gateway


[0.44: Buffered SSE 延迟与部署适用性](docs/zh-CN/latency.md)

## Least Privilege, Least Agency

**最小权限限制访问，最小自主性约束自主行动。**

我们的设计原则：仅授予代理所需的访问权限，并限定其独立行动的范围。TrapDefense 补充现有 IAM 和目标服务权限，对经网关路由的受支持调用执行操作和数据策略。可选的代理身份支持按代理设置权限范围、委托和审批控制。

[0.44: 运维工作区（0.44）](docs/zh-CN/operator-workspace.md)


[0.42: 模型 → MCP → 模型验证](docs/zh-CN/agent-workflow.md)

**0.44:** [模型提供商连接](docs/zh-CN/providers.md) — OpenAI · Anthropic · Gemini · OpenRouter.

**通过明确的安全边界连接受支持的 HTTP API 和远程 MCP 服务器。需要逐代理控制时添加代理身份。**

[连接、识别、控制、验证 →](docs/zh-CN/aisg.md)

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Français](README.fr.md)

> **Open Source Preview 0.44：**完整运行时与运维界面采用 MIT 许可证。内置 Agent Access Broker 已实现并通过合成验证；在真实 IdP、客户策略、HA 和容量验证完成前仍标记为 **Experimental**。

TrapDefense 是用于受支持 HTTP 与 MCP 流量的自托管 AI Firewall。它检查请求和响应，执行 action、PII 与 secret 策略，保存脱敏证据，并可根据已注册的 agent、delegation、task、resource、action 与一次性人工审批进行授权。

```text
AI agent → 认证网关 → 可信请求绑定 → Envoy + inspector
         → 可选内置 Access Broker → Tool / MCP / HTTP API
```

## 控制台预览

使用合成数据的实际 0.41 界面。仪表板包含人为设置的七秒提供商延迟测试，并非性能基准。Agent 管理来自独立的本地演示。

![运行时仪表板](docs/assets/console-dashboard-041.png)

<table>
<tr>
<td width="50%"><img src="docs/assets/console-agents-041.png" alt="Agent 权限 · 实验性"><br><strong>Agent 权限 · 实验性</strong></td>
<td width="50%"><img src="docs/assets/console-provider-041.png" alt="提供商连接设置"><br><strong>提供商连接设置</strong></td>
</tr>
</table>

## 单一开源产品

不再区分 Community 与 Enterprise 代码版本。本公开仓库包含 Runtime Gateway、HTTP/MCP 检查、PII/secret 防护、外部 OAuth JWT 验证、Agent Registry、delegation、Access Broker、人工审批、审计、运维控制台和 Docker 自托管。运行时不需要私有软件包。

未来付费服务可以包括托管云、fleet 运维、多节点 HA、外部不可变审计、客户集成与支持；当前开源执行功能不会被许可证门槛隐藏。[开源产品模型](docs/zh-CN/editions.md)

## Docker 自托管

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
```

在 `http://localhost:18080` 使用初始化时设置的 admin 密码登录。客户端必须能配置 HTTP/MCP URL，以及 `X-TD-Client-Key` 或 Bearer JWT。目标服务凭据独立管理；一个安装实例只连接一个固定目标，并使用显式 route/tool 映射。[自托管说明](docs/zh-CN/self-hosting.md)

## 内置 Access Broker（Experimental）

仅网关模式验证转发来源并执行本地检查策略，不声明 agent identity。Broker 模式要求外部 IdP 签发的 JWT 与显式 claim mapping。TrapDefense 只把经过验证且已配置的 claims 映射为 `tenant_id`、`user_id`、`agent_id`、`delegation_id` 和 `task_id`；缺少必需身份信息时会在转发前拒绝请求。

Broker 检查 tenant、registry、tool/resource 范围、delegation、user、task、action、request digest 与 approval。高风险 action 返回 `approval_required`，批准后的请求只能精确使用一次。TrapDefense 不替代目标服务权限，也不签发下游 OAuth token。

## 本地演示与验证

```bash
./scripts/install-console.sh
./scripts/run-console.sh
```

打开 [http://127.0.0.1:5176](http://127.0.0.1:5176)，使用 `admin` / `1234` 登录并立即修改密码。演示把合成 agent 与 delegation 写入真实文件型 Broker，并展示“需要审批 → 审批 → 一次执行 → 重放被阻止”。

```bash
pip install -e ".[dev]"
pytest -q
npm run check --prefix console
npm run build --prefix console
```

这些结果属于源码、协议和合成证据，并不等同于真实 Entra/Okta/Keycloak 租户、Conditional Access、客户 MCP 认证、生产路由、HA 或容量认证。

[控制台](docs/zh-CN/console.md) · [架构](docs/zh-CN/architecture.md) · [安全](docs/zh-CN/security.md) · [迁移](docs/zh-CN/migration.md) · [英文基准文档](README.md)

## 许可证

MIT。本仓库中的 Runtime Gateway 与 Access Broker 全部开源。
