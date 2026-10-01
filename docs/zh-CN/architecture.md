# 架构与信任边界

**安装路径：**Docker 部署请遵循[自托管指南](self-hosting.md)。独立源码控制台的 Entra SSO 和合成演示配置不会自动应用到 Docker。

> **AISG:** [连接、识别、控制、验证](aisg.md). 网关使用部署密钥或已验证 JWT。agent_key 无需外部 IAM 即可识别注册代理。JWT identity_mode: agent 使用已验证的租户和代理声明；delegated 还要求用户、任务和委托。现有代理默认需要委托。

[English](../en/architecture.md) · [한국어](../ko/architecture.md) · [简体中文](../zh-CN/architecture.md) · [日本語](../ja/architecture.md) · [Español](../es/architecture.md) · [Français](../fr/architecture.md)

> **0.47：**控制台（控制平面）与网关/检查器（数据平面）是独立进程。策略仅以 Ed25519 签名快照的形式进入数据平面，证据通过仅追加的 spool 返回。参见[平面分离](plane-separation.md)。

控制台支持单租户 Microsoft Entra ID SSO 以及管理员、查看者角色。控制台操作员身份与智能体授权是独立边界；智能体授权由内置 Access Broker 执行。 [Entra SSO](identity.md).

```text
AI agents → TrapDefense AI Firewall → Tools / MCP servers / APIs
            Action policy · Data protection · Audit
          ← Inspected responses ←
```

## 数据平面与管理平面

管理 API 认证本地操作员、保存策略并提供 UI。Envoy 转发支持的 HTTP/MCP 流量，通过 gRPC ExtProc 检查请求和响应。每条流保留自己的策略快照。无业务副作用的合成 HTTP 目标提供接收证据。参见[安装指南](console.md)。

## 信任契约

1. 在 TrapDefense 外强制路由，防止受保护流量绕过代理。
2. 在 TLS ingress 终止客户端 HTTPS，并使用内置签名适配器。外部 TLS 解密设备仅是独立网络集成的可选项，不是 base_url/MCP URL 部署的前提。
3. 可信适配器删除客户端提供的 `x-td-*`、`x-asr-*` 上下文，对实际观察到的请求签名。保留 method、authority、path/query、应用标头和完整正文。规范绑定及排除项见 `inspection/identity.py`。
4. HMAC 密钥仅留在可信节点和检查器，不分发给智能体。为 gateway-only 配置 `source_id` 允许列表。隔离明文及 ExtProc 链路；示例不认证公开 gRPC 监听器。
5. Envoy 使用完整缓冲、大小/时间上限和 `failure_mode_allow: false`，转发前移除证明标头。签名绑定原请求；若使用持久审批，则绑定脱敏后操作的摘要。
6. Gateway-only 模式应用显式的本地路由/工具/资源/操作规则并验证来源，不确认用户身份或智能体委托权限。
7. Broker 模式使用已验证的 JWT 身份 claims，并检查内置 registry、delegation、task、resource、action 与一次性 approval；缺少必需身份时 fail closed。

没有适配任意 TLS 设备的通用自动适配器。集成必须防止元数据伪造并限制直接访问上游。

## 支持范围与限制

路由必须精确匹配 authority、method、path 及要求的标头。MCP 支持显式映射的 JSON-RPC 调用和配置版本，不认证所有 MCP 功能。任意 MCP 传输、WebSocket 隧道、不透明加密正文、无限制 CONNECT 和自动流量发现均不包含。脱敏仅修改允许的字段或格式，不安全的变换关闭放行。签名规则只检测有限的已知模式，不保证阻止所有提示注入。SSE 缓冲完整且有界的流，不是无限逐 token 输出。

独立 mirror 收集器接收副本，不能阻断或改变原请求；仅标头的副本覆盖不完整。控制台 Mirror 在同步代理路径观察且不修改正文，但检查器通信故障仍会阻断。部署和报告必须区分两者。JSONL 检查证据和 SQLite 审计不保存原文或密钥，但属于可修改的本地存储，不是不可变合规留存。

## 网络配置

控制台使用回环与固定 digest 的 amd64/arm64 Envoy 镜像。macOS 通过 Docker Desktop 转发至主机，Linux 使用 host networking。NIC 清单是 OS 接口而非物理端口数量。双网卡路由、透明桥接、物理出口绑定、真实 IdP/TLS、HA 和生产性能需另行实现或验证。可选 agentgateway 运行测试属于兼容性验证，不是托管网关服务。
