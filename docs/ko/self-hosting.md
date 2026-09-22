# Docker 셀프호스팅 — 0.44 Open Source Preview

> **0.44:** [운영 작업 공간 (0.44)](operator-workspace.md)


> [모델 제공자 연결](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [연결 → 신원 → 통제 → 확인](aisg.md). Gateway 접속은 연결 키 또는 검증된 JWT로 인증합니다. 로컬 agent_key는 외부 IAM 없이 등록된 에이전트를 식별합니다. JWT identity_mode: agent는 검증된 테넌트·에이전트 정보를 사용하고, delegated는 사용자·작업·위임도 요구합니다. 기존 에이전트는 기본적으로 위임이 필요합니다.

[English](../en/self-hosting.md) · [한국어](../ko/self-hosting.md) · [简体中文](../zh-CN/self-hosting.md) · [日本語](../ja/self-hosting.md) · [Español](../es/self-hosting.md) · [Français](../fr/self-hosting.md)

## 0.44 시작 경로 선택

- **모델 API:** [제공사 프로필](providers.md)로 OpenAI·Anthropic·Gemini·OpenRouter를 연결합니다. SDK base URL을 변경하고 제공사 키는 게이트웨이에 보관합니다.
- **HTTP / MCP 도구:** 아래 Docker 예제로 시작한 뒤 합성 목적지를 명시적으로 매핑한 실제 서비스로 교체합니다.
- **전체 흐름 검증:** [두 에이전트 모델 → MCP → 모델 예제](agent-workflow.md)를 실행합니다. 기본 모드는 유료 키가 필요 없으며 실호출 증거와 합성 검증·측정 한계를 구분합니다.

게이트웨이 인증은 `client_key`, `agent_key`, 외부 `jwt`를 지원합니다. 로컬 Agent Registry와 agent_key를 통한 권한 통제는 선택 사항이며 대상 인증을 대체하지 않습니다. 설치별 목적지는 하나입니다. 모델과 별도 실행 도구는 각각 게이트웨이를 거쳐야 합니다. 모델 프로필의 SSE는 전체 버퍼링 후 검사·전달하며 실시간 토큰 스트리밍은 아닙니다.

0.44은 어댑터·Envoy·검사기·운영 UI와 분리된 게이트웨이/대상 인증을 함께 제공하는 Docker Compose Preview입니다. 이미지는 소스에서 로컬 빌드합니다. TrapDefense Cloud는 계획 단계이며 가입할 수 없습니다.

클라이언트에서 MCP/API URL을 바꾸고 `X-TD-Client-Key` 또는 OAuth Bearer JWT를 사용할 수 있어야 합니다. 설치별 목적지는 하나이며 경로·도구를 명시적으로 매핑합니다. 자세한 증거는 [호환성 표](gateway-compatibility.md)를 참고하세요.

| 구분 | 지원 범위 |
|---|---|
| HTTP API | JSON, 정확한 method/path, 최대 1 MiB, 유한 응답 |
| MCP | 무상태 JSON POST, 명시적으로 등록된 제어 메서드·도구 |
| 게이트웨이 인증 | 연결 키 또는 외부 IdP의 RS256 JWT 검증(issuer/audience/scope 및 RFC 9728 metadata) |
| 대상 인증 | none, 레거시 Bearer 전달, 파일 기반 고정 Bearer/API Key 주입 |
| 미지원 | OAuth 발급·로그인 중개·DCR·OBO, 쿠키/세션, 장시간 SSE, WebSocket, stdio, 폐쇄형 SaaS 내부 호출 |

관리자 비밀번호는 콘솔 로그인용입니다. 연결 키 또는 JWT는 TrapDefense 접근용입니다. JWT는 구성한 게이트웨이 audience에 대해 검증되며 대상으로 전달되지 않습니다. 대상 서비스는 별도 자격증명과 자체 권한을 검증합니다. 연결 키나 JWT 자체가 에이전트를 자동 등록하지는 않습니다. 에이전트 등록·권한은 선택한 Access Broker 모드에서 별도로 관리하며 OAuth 토큰 발급은 외부 IdP가 맡습니다.

## Docker

Git과 Docker Compose v2가 필요합니다. `init`에서 12자 이상 관리자 비밀번호를 지정합니다. 기본 비밀번호는 없습니다. 예제 설정은 합성 목적지를 사용하므로 실제 서비스 연동으로 오해하지 마세요.

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
docker compose run --rm app client-key
```

`http://localhost:18080`에 admin으로 로그인합니다. `client-key`로 연결 키를 확인해 클라이언트의 비밀 헤더 설정에 보관하세요. 게이트웨이는 `http://localhost:18084`입니다. 합성 목적지 토큰은 `Bearer synthetic-target-token`입니다.

실제 연결 시 `deployment.yaml`의 upstream·authority·경로·도구·resource를 바꾸세요. `gateway_auth`는 `client_key`, `agent_key` 또는 `jwt`, `target_auth`는 `none`, `passthrough_bearer`, `static_bearer`, `static_api_key`를 사용합니다. JWT와 passthrough는 함께 쓸 수 없습니다. 고정 자격증명은 UID 10001이 읽을 수 있는 0600 비밀 파일로 마운트하며 충돌하는 입력은 거부합니다.

UI는 정책·비밀번호를 관리합니다. 매핑 변경은 백업 후 `policy-reset`으로 기존 정책을 명시적으로 초기화하고 `render`와 재생성을 수행하세요. 계정·키·이벤트는 보존됩니다. 새 요청부터 정책이 적용됩니다.

기본 공개 주소는 루프백입니다. 원격 사용은 TLS 프록시와 정확한 `console_origin` 설정이 필요합니다. 검사기와 Envoy는 호스트에 포트를 공개하지 않습니다. 경로 우회 차단은 고객 네트워크에서 구성해야 합니다.

재시작 후 named volume의 정책·키·감사 기록은 유지됩니다. 중지 후 두 볼륨과 설정을 함께 백업하세요. `down -v`는 데이터를 삭제합니다. 롤백은 이전 이미지와 일치하는 백업을 함께 복원합니다. 리스너 정상만으로 연동 성공을 판단하지 말고 허용·차단 요청과 대상 효과를 확인하세요. 장시간 스트림·HA·실제 고객 IAM은 별도 검증 대상입니다.

[상세 설정·VS Code·검증 표](gateway-compatibility.md) · [Detailed examples, backup and migration (English)](../en/self-hosting.md)

## 내장 Access Broker 활성화

다음은 **delegated JWT 모드** 설정입니다. 로컬 agent_key와 무인 agent 모드는 [AISG 가이드](aisg.md)를 참조하세요.

`gateway_auth.mode: jwt`를 사용하고 `identity_claims`에 tenant, user, agent, delegation, task claim 이름을 명시하세요. 이어서 `access_broker.enabled: true`와 하나의 `access_broker.tenant_id`를 설정합니다. 콘솔에서 해당 tenant의 agent와 delegation을 먼저 등록해야 합니다. 필수 claim 누락과 tenant 불일치는 전달 전에 차단됩니다. 정확한 YAML 예시는 [영문 기준 문서](../en/self-hosting.md)를 따르세요. 로컬 file store는 동일 호스트용이며 multi-node HA가 아닙니다.

## 0.44 · Buffered SSE

[Buffered SSE 지연과 도입 적합성](latency.md)

게이트웨이는 지원되는 응답 전체를 수집·검사한 뒤 콘텐츠를 전달합니다. 첫 콘텐츠 지연에는 검사뿐 아니라 응답 수집도 포함됩니다. 완성된 결과를 기다릴 수 있는 작업에 적합하며, 대화형 채팅은 명시적인 지연 예산으로 평가해야 합니다.
