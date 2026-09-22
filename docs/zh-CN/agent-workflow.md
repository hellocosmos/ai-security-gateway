# 模型 → MCP → 模型验证 (0.44)

[English](../en/agent-workflow.md) · [한국어](../ko/agent-workflow.md) · [简体中文](../zh-CN/agent-workflow.md) · [日本語](../ja/agent-workflow.md) · [Español](../es/agent-workflow.md) · [Français](../fr/agent-workflow.md)

通过两个独立 Gateway 连接官方 OpenAI SDK 和 MCP 客户端。除了模型 base_url，还必须更改 MCP URL 才能控制工具执行。同一个 Agent ID 在两个 Gateway 上使用不同密钥。

默认使用脚本化合成模型，不进行真实推理或付费调用。通过实际 Docker、Envoy 和检查器验证 Agent A 读取成功、Agent B 读取被拒、删除被阻止、PII 脱敏、已使用密钥撤销及预设过期凭证。阻止原因和目标执行记录必须同时符合预期。

真实 OpenAI 验证需要显式模型 ID 和权限为 0600 的测试密钥文件。指定 --model 和 --provider-key-file 将使用合成业务数据进行付费 API 调用；失败不会回退为合成结果。2026-09-18 已通过真实 OpenAI `gpt-4.1-mini` 验证三个场景，每个场景调用模型两次。MCP 目标和业务数据仍为合成。此结果仅适用于该模型与账户，不代表所有供应商或生产环境认证。LLM 响应 Cookie 被移除；Chat Completions、OpenAI Responses 及支持的 SSE 信封中的有限范围整数创建时间戳作为协议元数据处理，嵌套业务字段仍接受检查。

仅清理自动创建的测试项目。本示例不验证 HA、性能、实时流式传输或取消请求。完整命令与限制见英文指南。

```bash
pip install -e '.[dev,console,compat,llm-compat]'
python -m examples.agent_workflow --report .runtime-state/workflow-042.json
```

[Full setup / live mode / evidence](../en/agent-workflow.md)


## 0.42

扩展验证涵盖实际本地 MCP 服务器文档操作与检查器故障、同机工作进程恢复与重放防护，以及四种供应商 SDK 的合成合同。不是客户 MCP、其他供应商真实账户或跨主机 HA 认证。按每用户 0.1 RPS 的五秒本地测试，10 和 30 RPS 符合预期，50 RPS 起出现 503。样本未出现被禁止的删除或 PII 泄露。这不是容量保证或硬件建议；详细数据见英文文档。

[Detailed qualification and measurements](../en/agent-workflow.md#042-extended-qualification)

SSE 追加验证：分成两个延迟片段的邮箱被重组并脱敏后才交付。客户端超时后合成供应商仍完成生成，不保证立即取消上游任务。
