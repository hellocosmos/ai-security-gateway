# 模型提供商连接 (0.45)

[English](../en/providers.md) · [한국어](../ko/providers.md) · [简体中文](../zh-CN/providers.md) · [日本語](../ja/providers.md) · [Español](../es/providers.md) · [Français](../fr/providers.md)

保留现有 SDK 和 API 格式，只更改 base_url 和 api_key。SDK api_key 使用网关连接密钥或可选的独立代理凭证；真实提供商密钥保存在网关服务器。

每个部署仅连接一个提供商，使用明确的模型允许列表和精确路径。多个提供商使用独立 Compose 项目、端口和状态卷。

SSE 完整缓冲并检查后按原始事件格式传递，不是实时逐词输出。默认限制 120 秒、1 MiB；不完整或不支持的响应会被阻止。

支持文本及客户端执行的函数调用。不支持文件、媒体、提供商端工具、WebSocket、加密推理及 Gemini thought signature。要控制真正的工具执行，必须另行连接 HTTP/MCP 路径。

需要按代理控制时启用 agent_key 和 Broker，在控制台注册代理工具权限并明确允许自主执行，然后签发凭证，填入同一个 SDK api_key 参数。

配置位于 deploy/selfhost/providers/。将 YOUR_MODEL_ID 替换为实际可用模型，并安全保存提供商密钥到 /state/provider-key。验证使用官方 Python SDK 和合成服务，不代表真实提供商全部功能认证。

| Provider | Gateway base_url | API |
| --- | --- | --- |
| OpenAI | https://gateway.example.com/v1 | Chat Completions / Responses |
| Anthropic | https://gateway.example.com | Messages |
| Gemini native | https://gateway.example.com | v1beta generateContent / streamGenerateContent |
| Gemini OpenAI | https://gateway.example.com/v1beta/openai | Chat Completions |
| OpenRouter | https://gateway.example.com/api/v1 | Chat Completions |


[SDK examples / Docker commands](../en/providers.md) · [AISG](aisg.md)

## 0.44 · Buffered SSE

[Buffered SSE 延迟与部署适用性](latency.md)

网关收集并检查完整的受支持响应后才交付内容。首内容延迟包括收集与检查，不只是扫描时间。适合能等待完整结果的任务；交互聊天需按明确的延迟预算评估。
