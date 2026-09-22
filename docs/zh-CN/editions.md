# 单一开源产品

> **AISG:** [连接、识别、控制、验证](aisg.md). 网关使用部署密钥或已验证 JWT。agent_key 无需外部 IAM 即可识别注册代理。JWT identity_mode: agent 使用已验证的租户和代理声明；delegated 还要求用户、任务和委托。现有代理默认需要委托。

[English](../en/editions.md) · [한국어](../ko/editions.md) · [简体中文](../zh-CN/editions.md) · [日本語](../ja/editions.md) · [Español](../es/editions.md) · [Français](../fr/editions.md)

TrapDefense 0.44 使用一个 MIT 许可代码库。Runtime Gateway 与 Agent Access Broker 一同发布在本公开仓库中，不需要私有 Python 包、provider entry point、license key 或 edition switch。

## 发布状态

| 边界 | 状态 | 证据与限制 |
|---|---|---|
| Runtime Gateway 与控制台 | **Open Source Preview** | 提供公开源码、CI、合成 Envoy 路径、HTTP/MCP 策略、PII/secret 控制和本地运维 UI。生产路由与容量需按环境验证。 |
| 内置 Agent Access Broker | **Experimental** | 已公开 registry、delegation、严格授权、tenant 隔离、文件事务和请求绑定的一次性审批。真实客户 IdP/策略与多节点验证仍待完成。 |
| Docker 自托管 | **Preview** | 从源码构建 adapter、Envoy、inspector、console、gateway 认证与独立目标凭据。每个安装实例使用一个固定目标。 |
| Managed cloud、fleet、多节点 HA、外部不可变审计 | **Planned** | 尚未发布，也不会表述为当前可用。 |

仅网关模式执行本地检查与可信来源验证。启用 Broker 后增加已验证 JWT 身份映射、agent registry、delegation、resource/action 授权和 approval。两种模式使用同一开源软件包。

未来付费方向可以运营同一开源 runtime，提供 managed service、fleet 生命周期、多节点 HA、外部审计、客户 connector、策略上线、SLA 与支持。这是服务与运维边界，不是源码功能门槛。

文件 store 通过 atomic replace 与 file lock 支持同主机 POSIX 进程，但不是分布式数据库，不能作为 NFS/SMB 多主机 HA。合成测试不等同于真实 IdP、Conditional Access、客户 MCP 认证、TLS 路由或容量认证。

[Docker 0.44](self-hosting.md) · [架构](architecture.md) · [安全](security.md) · [兼容性](gateway-compatibility.md)
