# Model provider connections (0.46)

[English](../en/providers.md) · [한국어](../ko/providers.md) · [简体中文](../zh-CN/providers.md) · [日本語](../ja/providers.md) · [Español](../es/providers.md) · [Français](../fr/providers.md)

Keep the provider's native SDK and request format. Change its base URL and use a TrapDefense connection key, or an individual agent credential, as the SDK `api_key`. The actual provider key stays on the gateway. Agent identity is optional; authenticated gateway admission is always required.

## Supported profiles

| Profile | SDK base URL on your gateway | Supported calls |
| --- | --- | --- |
| OpenAI | `https://gateway.example.com/v1` | Chat Completions, Responses |
| Anthropic | `https://gateway.example.com` | Messages |
| Google Gemini, native | `https://gateway.example.com` with API version `v1beta` | generateContent, streamGenerateContent |
| Google Gemini, OpenAI-compatible | `https://gateway.example.com/v1beta/openai` | Chat Completions |
| OpenRouter | `https://gateway.example.com/api/v1` | OpenAI-compatible Chat Completions |

One deployment serves **one provider origin**. Use separate Compose project names, ports, state volumes and hostnames for multiple providers. This version does not translate one provider's payload into another provider's API or route arbitrary destinations supplied by a client.

## Start a provider deployment

```bash
cd deploy/selfhost
export TD_CONFIG_FILE=./providers/openai.yaml  # anthropic.yaml, google.yaml, openrouter.yaml
# Edit this file: replace YOUR_MODEL_ID with exact model IDs available to your account.
docker compose build app
docker compose run --rm app init
# Prepare provider-key locally outside the repository, with owner-only permissions.
# Import without putting the key in a command argument or Docker environment.
docker compose run --rm -T --entrypoint sh app -c 'umask 077; cat > /state/provider-key' < /secure/path/provider-key
docker compose up -d
# Displays a secret: save it in your client's secret manager, not in source code.
docker compose run --rm app client-key
```

The provider files generate exact HTTPS origins and routes. Unknown models/routes fail closed. The default is a 120-second provider budget (10–300 seconds configurable), a 1 MiB body limit and bounded concurrency. Existing HTTP/MCP deployments retain their defaults. Production public listeners require your TLS ingress and the matching `console_origin`; default ports bind localhost only.

Each provider's SDK credential slot is accepted: Bearer, Anthropic `x-api-key`, or Gemini `x-goog-api-key`. Multiple credential slots are rejected. These values authenticate the **gateway** and are replaced with its configured provider key. API keys in query strings are rejected; native Gemini streaming accepts only `alt=sse`. No gateway credential is forwarded upstream.

## Native SDK examples

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:18084/v1",  # OpenAI profile
    api_key=os.environ["TD_GATEWAY_KEY"],
    timeout=130.0,
)
response = client.responses.create(model=os.environ["MODEL_ID"], input="Hello")
print(response.output_text)
# Chat: client.chat.completions.create(model=..., messages=[...], stream=True)
# OpenRouter: base_url="http://localhost:18084/api/v1"
# Gemini compatibility: base_url="http://localhost:18084/v1beta/openai"
```

```python
import os
from anthropic import Anthropic

client = Anthropic(base_url="http://localhost:18084",
                   api_key=os.environ["TD_GATEWAY_KEY"], timeout=130.0)
with client.messages.stream(model=os.environ["MODEL_ID"], max_tokens=256,
                            messages=[{"role": "user", "content": "Hello"}]) as stream:
    print(stream.get_final_message())
```

```python
import os
from google import genai

client = genai.Client(api_key=os.environ["TD_GATEWAY_KEY"],
                     http_options={"base_url": "http://localhost:18084",
                                   "api_version": "v1beta", "timeout": 130000})
for part in client.models.generate_content_stream(model=os.environ["MODEL_ID"], contents="Hello"):
    print(part.text)
```

JavaScript SDK compatibility has not been exercised. The verification below covers the listed Python SDKs and supported wire contracts.

## Optional per-agent authorization

Add to the selected provider YAML:

```yaml
gateway_auth:
  mode: agent_key
access_broker:
  enabled: true
  tenant_id: local
```

Recreate the app, register an agent in the console, grant the relevant `llm.chat`, `llm.responses`, `llm.messages` or `llm.generate` tool, explicitly enable autonomous access, and issue a credential. Put that credential in the same SDK `api_key` parameter. Console grants cover the configured model allowlist; changing that list does not automatically expand existing agent grants. External JWT mode remains available with explicit claim mapping. User/task delegation is required only in delegated mode.

## Streaming and security boundaries

**SSE is buffered, inspected in full, then delivered in its native event format. This is not real-time token streaming.** This prevents a secret or PII split across chunks from escaping before a later chunk completes it. In inline mode, unknown, malformed, oversized, timed-out or incomplete streams fail closed. Mirror mode remains observational and does not enforce content verdicts. Clients must allow the configured full-response wait. A 0.42 synthetic TLS test confirmed that the upstream completed after a client timeout. Immediate upstream generation cancellation is not guaranteed; an abandoned generation may continue until completion or the configured timeout.

The verified subset is text and client-executed function calls, including JSON arguments, ordinary responses and bounded SSE. Files/uploads, images/audio/video, realtime/WebSocket, provider-executed tools, background/stored conversation retrieval, encrypted reasoning, Gemini thought signatures and partial-argument extensions are not supported. Unknown SSE event extensions can be rejected. Provider authentication failures and HTTP rate-limit statuses are preserved when their response is inspectable.

A returned function call is a **proposal**, not proof that a tool was executed. Route the actual tool HTTP/MCP connection through TrapDefense separately to enforce action-time policy. A model base URL change does not intercept tools executed elsewhere.

## Verification

`pip install -e '.[dev,console,llm-compat]'` then `pytest tests/test_provider_compat.py -q` runs official OpenAI 3.14.1, Anthropic 1.6.0 and google-genai 2.24.0 against local synthetic provider contracts through gateway authentication and the inspection engine. Tests include both connection-key and agent-key modes. They do not call paid APIs and are not certification of every live provider feature or model.

On 2026-09-17, a separate local Docker smoke also exercised all four profiles through real Envoy and synthetic TLS origins, including a seven-second provider response. This validates local transport and contract handling, not live provider accounts.

Official references: [OpenAI SDK](https://github.com/openai/openai-python), [Claude API](https://platform.claude.com/docs/en/api/overview), [Gemini API](https://ai.google.dev/api/generate-content), [Gemini SDK](https://github.com/googleapis/python-genai), [OpenRouter](https://openrouter.ai/docs/quickstart).


### 0.42 qualification update

See the [agent workflow](agent-workflow.md) for the live OpenAI model-to-MCP result, response-cookie and timestamp handling, and measured operating limits. Other live provider accounts remain unqualified.

## 0.44 · Buffered SSE

[Buffered SSE latency and rollout fit](latency.md)

The gateway collects and inspects the complete supported response before delivering content. Client first-content latency includes collection and inspection, not just scanner time. This suits workflows that can wait for a complete result; interactive chat must be tested against an explicit latency budget.
