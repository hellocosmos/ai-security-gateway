# 모델 제공자 연결 (0.45)

[English](../en/providers.md) · [한국어](../ko/providers.md) · [简体中文](../zh-CN/providers.md) · [日本語](../ja/providers.md) · [Español](../es/providers.md) · [Français](../fr/providers.md)

기존 SDK와 API 형식을 유지하고 base_url과 api_key 설정만 변경합니다. SDK api_key에는 Gateway 연결 키 또는 선택적 개별 Agent 자격증명을 넣습니다. 실제 제공자 키는 Gateway 서버에 보관합니다.

설치별 제공자는 하나이며, 모델 허용 목록과 정확한 경로를 사용합니다. 여러 제공자는 별도 Compose 프로젝트·포트·상태 볼륨으로 실행합니다.

SSE는 전체 응답을 버퍼링하고 검사한 뒤 원래 이벤트 형식으로 전달합니다. 실시간 토큰 전달이 아닙니다. 기본 120초·1 MiB 제한이며, 불완전하거나 지원하지 않는 응답은 차단합니다.

텍스트와 클라이언트 측 함수 호출을 지원합니다. 파일·미디어·제공자 측 도구·WebSocket·암호화 추론·Gemini thought signature는 지원 범위 밖입니다. 실제 도구 실행은 별도의 HTTP/MCP 경로를 연결해야 통제할 수 있습니다.

Agent별 통제가 필요하면 agent_key 모드와 Broker를 켜고, 콘솔에서 Agent·도구 권한·무인 실행 허용을 등록한 뒤 키를 발급합니다. 그 키를 동일한 SDK api_key에 넣습니다.

설정 파일은 deploy/selfhost/providers/에 있습니다. YOUR_MODEL_ID를 사용 가능한 실제 모델 ID로 교체하고 제공자 키를 /state/provider-key에 안전하게 넣으세요. 공식 Python SDK 합성 검증이며 실제 제공자의 모든 기능을 인증한 것은 아닙니다.

| Provider | Gateway base_url | API |
| --- | --- | --- |
| OpenAI | https://gateway.example.com/v1 | Chat Completions / Responses |
| Anthropic | https://gateway.example.com | Messages |
| Gemini native | https://gateway.example.com | v1beta generateContent / streamGenerateContent |
| Gemini OpenAI | https://gateway.example.com/v1beta/openai | Chat Completions |
| OpenRouter | https://gateway.example.com/api/v1 | Chat Completions |


[SDK examples / Docker commands](../en/providers.md) · [AISG](aisg.md)

## 0.44 · Buffered SSE

[Buffered SSE 지연과 도입 적합성](latency.md)

게이트웨이는 지원되는 응답 전체를 수집·검사한 뒤 콘텐츠를 전달합니다. 첫 콘텐츠 지연에는 검사뿐 아니라 응답 수집도 포함됩니다. 완성된 결과를 기다릴 수 있는 작업에 적합하며, 대화형 채팅은 명시적인 지연 예산으로 평가해야 합니다.
