# 게이트웨이 클라이언트 호환성 — 0.45

> [모델 제공자 연결](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [연결 → 신원 → 통제 → 확인](aisg.md). Gateway 접속은 연결 키 또는 검증된 JWT로 인증합니다. 로컬 agent_key는 외부 IAM 없이 등록된 에이전트를 식별합니다. JWT identity_mode: agent는 검증된 테넌트·에이전트 정보를 사용하고, delegated는 사용자·작업·위임도 요구합니다. 기존 에이전트는 기본적으로 위임이 필요합니다.

[English](../en/gateway-compatibility.md) · [한국어](../ko/gateway-compatibility.md) · [简体中文](../zh-CN/gateway-compatibility.md) · [日本語](../ja/gateway-compatibility.md) · [Español](../es/gateway-compatibility.md) · [Français](../fr/gateway-compatibility.md)

클라이언트는 원격 HTTP/MCP URL을 TrapDefense로 바꾸고 연결 키 헤더 또는 OAuth Bearer JWT를 사용할 수 있어야 합니다. 클라이언트→TrapDefense 인증과 TrapDefense→대상 인증은 분리됩니다.

| 경로 | 0.42 증거 |
|---|---|
| 일반 JSON HTTP | HTTPX 합성 통합 검증 완료 |
| 공식 Python MCP SDK 1.30.0 | MCP `2025-11-25` 초기화·알림·도구 목록 합성 통합 검증 완료 |
| Entra 유사 OAuth | `scp`·`tid`·`oid`·`azp`, discovery·DCR·PKCE·resource binding을 합성 검증. 실제 Entra 테넌트는 미검증 |
| Okta 유사 OAuth | 배열형 `scp`와 `cid`를 같은 전체 흐름으로 합성 검증. 실제 Okta 서버는 미검증 |
| Keycloak 유사/실제 로컬 | 합성 전체 흐름과 별도로, digest 고정 공식 Keycloak 26.7.3 컨테이너가 발급한 실제 로컬 토큰 및 discovery/JWKS 검증 완료 |
| VS Code 1.135 원격 MCP | 실제 설치 제품에서 `Running`, 도구 1개 발견, `initialize`·`notifications/initialized`·`tools/list` receipt와 MCP `2025-11-25` 요청 확인 |
| 세션 MCP·장기 SSE·WebSocket·stdio | 미지원. 세션 헤더와 upstream SSE는 fail-closed |
| 다중 노드 HA | 미지원. 현재 로컬 SQLite·replay·audit 상태를 가진 단일 gateway 구성 |

`gateway_auth`는 `client_key` 또는 `jwt`를 사용합니다. JWT 모드에서 TrapDefense는 OAuth Resource Server로 동작하며 RFC 9728 메타데이터와 `WWW-Authenticate` challenge를 제공합니다. `scope`/`scp`는 공백 구분 문자열 또는 문자열 배열을 허용하고, 선택적 `authorized_parties`는 `azp`·`appid`·`cid`를 제한합니다. Entra의 `roles` app role은 0.42에서 scope로 해석하지 않습니다.

`target_auth`는 `none`, `passthrough_bearer`, `static_bearer`, `static_api_key`를 지원합니다. JWT 게이트웨이 토큰은 대상에 전달되지 않습니다. 로그인·토큰 발급·refresh·OBO는 외부 IdP 또는 별도 credential provider가 담당합니다.

실제 연동 승인 전 URL 변경, 양쪽 인증, MCP 초기화/도구 조회, 허용·차단, 대상 부작용, PII/secret, 대상 401, 검사 장애와 직접 URL fallback 여부를 함께 확인하세요. 재현 명령·설정·출처는 [영문 가이드](../en/gateway-compatibility.md)를 참고하세요.


현재 검증은 실제 OpenAI→합성 MCP 흐름, 제공사 공식 SDK 합성 테스트, 실제 로컬 MCP·Keycloak과 VS Code 초기화·검색 증거를 포함합니다. 모델 SSE는 전체 버퍼링하며 상태 유지 MCP·고객 IAM 정책·서버 간 HA·운영 용량은 인증하지 않습니다. [0.42 검증과 한계](agent-workflow.md)를 확인하세요.
