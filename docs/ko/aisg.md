# TrapDefense — AI Security Gateway (0.46)

> [모델 제공자 연결](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

[en](../en/aisg.md) · [ko](../ko/aisg.md) · [zh-CN](../zh-CN/aisg.md) · [ja](../ja/aisg.md) · [es](../es/aisg.md) · [fr](../fr/aisg.md)

지원되는 HTTP API와 원격 MCP 서버를 명시적인 보안 경로로 연결합니다. 에이전트별 통제가 필요하면 신원을 추가합니다.

## 연결 → 신원 → 통제 → 확인

Docker 합성 환경을 실행하고 Access Broker에서 에이전트를 등록한 뒤 선택한 도구에 무인 접근을 허용하고 자격증명을 발급합니다. 클라이언트 URL을 바꾸고 Authorization 헤더에 자격증명을 전달합니다. 허용·차단 요청을 각각 보내 결정 기록을 확인하세요.

## 신원 방식 선택

Gateway 접속은 연결 키 또는 검증된 JWT로 인증합니다. 로컬 agent_key는 외부 IAM 없이 등록된 에이전트를 식별합니다. JWT identity_mode: agent는 검증된 테넌트·에이전트 정보를 사용하고, delegated는 사용자·작업·위임도 요구합니다. 기존 에이전트는 기본적으로 위임이 필요합니다.

## 자격증명 수명주기

로컬 자격증명은 1시간, 24시간 또는 최대 30일 후 만료됩니다. 해시만 저장하고 새 원문은 UI에서 한 번 표시합니다. 교체는 이전 키를 즉시 폐기합니다. 폐기·에이전트 비활성화는 이후 인증을 차단합니다. Gateway 자격증명은 대상 서비스 자격증명과 별개입니다.

## 호환성과 범위

설치당 고정 목적지 하나, 명시적으로 매핑한 HTTP JSON 및 무상태 MCP JSON POST를 지원합니다. SSE·상태 세션·stdio·WebSocket·SaaS 내부 호출은 지원하지 않습니다. 모델 API base_url 변경만으로 별도 실행 도구는 통제되지 않습니다. 각 보호 대상 URL과 고객 네트워크 우회 차단을 설정하세요.

## 승인

무인 접근도 도구·리소스·작업 권한을 검사합니다. 고위험 작업은 만료와 요청 결합이 있는 승인이 필요합니다. 검토 후 동일한 로컬 키 요청에 X-TD-Approval-ID를 추가해 재시도하면 한 번만 소비됩니다. Mirror 평가는 승인을 생성하거나 소비하지 않습니다.

## 검증 범위

로컬 합성 검증은 운영 IdP·고객 트래픽·HA·용량 인증이 아닙니다. Access Broker는 실험 단계이며 Managed Cloud 가입 서비스는 제공하지 않습니다.

## 빠른 시작

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
