# Buffered SSE 延迟与部署适用性 — 0.44

[en](../en/latency.md) · [ko](../ko/latency.md) · [zh-CN](../zh-CN/latency.md) · [ja](../ja/latency.md) · [es](../es/latency.md) · [fr](../fr/latency.md)

网关收集并检查完整的受支持响应后才交付内容。首内容延迟包括收集与检查，不只是扫描时间。适合能等待完整结果的任务；交互聊天需按明确的延迟预算评估。

## 复现

需要 Docker、Python 3.11+ 和项目 console 依赖。命令构建临时栈，不使用真实凭据或付费 API，并在 finally 中删除容器和卷。部署前在空闲主机上至少重复三次。

```bash
python -m pip install -e ".[console,compat,llm-compat]"
python -m examples.latency.benchmark --output /tmp/latency.json
```

## 首内容 p95 / 完成 p95 (ms)

2026-09-22 · synthetic fixture · short: 8 × 65 bytes content; long: 32 × 515 bytes content · 20 ms/chunk.

| Scenario | Concurrency | Direct | Gateway |
|---|---:|---:|---:|
| short | 1 | 56 / 202 | 232 / 233 |
| short | 8 | 58 / 197 | 420 / 421 |
| short | 32 | 97 / 219 | 1253 / 1253 |
| long | 1 | 53 / 752 | 822 / 822 |
| long | 8 | 69 / 745 | 1164 / 1164 |
| long | 32 | 89 / 726 | 3014 / 3014 |

这是 Docker ARM64、14 CPU、7.75 GiB 内存上的一次合成运行，不是最低硬件要求或按用户数的容量承诺。每项 12–64 个样本，p95 仅供描述，不是 SLA。直连使用 TLS，本地网关入口为 HTTP，上游为 TLS。未配置提供商凭据，因此 0.44 未运行真实模型；以往真实模型证据保留原日期。

## 解读

控制台显示当前进程各阶段最近 256 个样本。网关计时在客户端收到内容之前结束。Envoy 往返包括请求检查、上游收集、响应检查和传输。检查包含工作队列等待。这些分布包含失败，没有逐请求关联，不能相减，重启后清空。无样本表示未测量，不是零。

## 边界

64 个并发请求中完成 32 个，32 个返回 HTTP 503；没有不完整的 HTTP 200 SSE。分片邮件 PII 已脱敏。测试专用 32 KiB 限制下，超大输出返回 HTTP 500，10 秒超时返回 504，均无内容令牌。无效凭据返回 401。状态码不能单独定位故障组件，生产默认值不同。

## 证据限制

[JSON](../evidence/latency-044-synthetic.json) · [运维指南](operator-workspace.md)


| Docker sampled resource | Peak CPU (100% = one core) | Peak memory (MiB) |
|---|---:|---:|
| App / Python inspector | 87.8% | 148.9 |
| Envoy | 3.91% | 37.38 |
| Synthetic fixture | 17.87% | 21.77 |

表中为整个运行的采样峰值，不是各场景资源预留或推荐规格，可能遗漏短峰值。合成源在同一 Docker 主机，不是语言性能对比。并发增加会增加排队与检查，但不能证明 Python 是原因或 Go/Rust 会消除缓冲延迟。后台任务按完成 p95、错误率与期限评估；聊天按首内容 p95 与体验预算评估。在目标主机重复测试典型响应、策略、突发拒绝及恢复，并考虑客户端取消后上游仍可能继续生成。按实际并发、大小、请求率和策略成本估算，不按员工人数换算硬件。
