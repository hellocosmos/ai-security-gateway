# 本地性能基线

[English](../en/benchmark.md) · [한국어](../ko/benchmark.md) · [简体中文](../zh-CN/benchmark.md) · [日本語](../ja/benchmark.md) · [Español](../es/benchmark.md) · [Français](../fr/benchmark.md)

此命令通过已安装的 Envoy 监听器、gRPC ExtProc 检查器和合成 HTTP 目标测量可复现的**合成本地基线**。它用于在同一主机上比较版本回归，不代表生产容量、高可用或客户流量认证。

## 运行

先用 `./scripts/install-console.sh` 安装。基准测试占用相同的回环端口，因此运行前请停止控制台。

```bash
.venv/bin/trapdefense-benchmark --scenario read --iterations 30
```

场景包括 `read`、`pii`、`secret` 和 `response`。迭代次数限制为 5–500，预热为 0–50；默认预热 3 次后测量 30 次。每个请求都经过代理并生成净化后的决策证据，不使用外部业务目标或模型 API。

## 解释 JSON

`p50_ms`、`p95_ms`、`mean_ms` 和 `sequential_requests_per_second` 仅用于本地回归参考。决策和 HTTP 状态计数可确认测量期间预期结果没有静默变化。报告包含操作系统、架构、Python 版本和逻辑 CPU 数，但不包含主机名或检查内容。

仅在主机负载、Docker 版本、电源模式、场景、迭代数和策略相同的情况下比较结果。建议至少运行三次并保留中位结果。并发容量、连接复用、大正文、持续 SSE、故障恢复和多节点行为需要单独测试。

参见[控制台](console.md)、[架构](architecture.md)、[版本](editions.md)和[安全范围](security.md)。

## AI Firewall 检查器进程池

[AI Firewall 检查器进程池](inspector-pool.md)

## 0.44 · Buffered SSE

[Buffered SSE 延迟与部署适用性](latency.md)

网关收集并检查完整的受支持响应后才交付内容。首内容延迟包括收集与检查，不只是扫描时间。适合能等待完整结果的任务；交互聊天需按明确的延迟预算评估。
