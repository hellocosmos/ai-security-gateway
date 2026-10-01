# 아키텍처와 신뢰 경계

**설치 경로:** Docker 배포는 [설치 가이드](self-hosting.md)를 따릅니다. 별도 소스 콘솔의 Entra SSO·합성 데모 설정은 Docker에 자동 적용되지 않습니다.

> **AISG:** [연결 → 신원 → 통제 → 확인](aisg.md). Gateway 접속은 연결 키 또는 검증된 JWT로 인증합니다. 로컬 agent_key는 외부 IAM 없이 등록된 에이전트를 식별합니다. JWT identity_mode: agent는 검증된 테넌트·에이전트 정보를 사용하고, delegated는 사용자·작업·위임도 요구합니다. 기존 에이전트는 기본적으로 위임이 필요합니다.

[English](../en/architecture.md) · [한국어](../ko/architecture.md) · [简体中文](../zh-CN/architecture.md) · [日本語](../ja/architecture.md) · [Español](../es/architecture.md) · [Français](../fr/architecture.md)

> **0.47:** 콘솔(control plane)과 게이트웨이·inspector(data plane)는 별도 프로세스입니다. 정책은 Ed25519로 서명된 스냅샷으로만 data plane에 전달되고, 증거는 append-only spool로 돌아옵니다. [Plane 분리](plane-separation.md)를 참고하세요.

콘솔은 관리자·조회자 역할의 단일 테넌트 Microsoft Entra ID SSO를 지원합니다. 콘솔 운영자 인증과 에이전트 인가는 별도 경계이며, 에이전트 인가는 내장 Access Broker가 담당합니다. [Entra SSO](identity.md).

```text
AI agents → TrapDefense AI Firewall → Tools / MCP servers / APIs
            Action policy · Data protection · Audit
          ← Inspected responses ←
```

## 데이터 경로와 관리 경로

관리 API는 로컬 운영자를 인증하고 정책을 저장하며 UI를 제공합니다. Envoy는 지원하는 HTTP/MCP 요청을 전달하며 gRPC ExtProc로 요청·응답 검사를 호출합니다. 각 스트림은 적용 시점의 정책을 유지합니다. 무해한 합성 HTTP 목적지가 수신 증거를 제공합니다. [설치 안내](console.md)를 참고하세요.

## 신뢰 계약

1. 보호 트래픽이 우회하지 못하도록 TrapDefense 외부에서 경로를 강제합니다.
2. 클라이언트 HTTPS는 TLS ingress에서 종료하고 내장 서명 어댑터를 사용합니다. 외부 TLS 복호화 장비는 별도 네트워크 연동 시의 선택 사항이며 base_url/MCP URL 구성의 필수 조건이 아닙니다.
3. 신뢰된 어댑터가 클라이언트의 `x-td-*`, `x-asr-*` 문맥을 제거하고 실제 관찰한 요청에 서명합니다. method·authority·path/query·애플리케이션 헤더·전체 본문을 보존합니다. 결합 규칙과 제외 항목은 `inspection/identity.py`에 정의합니다.
4. HMAC 키는 신뢰된 홉과 검사기에만 보관하고 에이전트에 배포하지 않습니다. gateway-only `source_id`를 허용 목록에 등록합니다. 평문·ExtProc 구간을 격리하세요. 예제는 공개 gRPC 리스너를 인증하지 않습니다.
5. Envoy는 본문 전체 버퍼링, 크기·시간 상한, `failure_mode_allow: false`를 사용하며 전달 전 서명 헤더를 제거합니다. 서명은 원본 요청에, 영속 승인은 제공되는 경우 마스킹 후 동작 digest에 결합됩니다.
6. Gateway-only 모드는 경로·도구·리소스·행위의 명시적 로컬 규칙과 전달 출처를 검증합니다. 사용자 인증이나 에이전트 위임 권한을 보증하지 않습니다.
7. Broker 모드는 검증된 JWT identity claim과 내장 registry, delegation, task, resource, action, 일회성 approval을 평가합니다. 필수 identity가 없으면 fail closed 합니다.

모든 TLS 장비에 자동 적용되는 범용 어댑터는 없습니다. 통합 시 메타데이터 위조와 목적지 직접 접근을 차단해야 합니다.

## 지원 범위와 한계

경로는 정확한 authority·method·path·필수 헤더에 일치해야 합니다. MCP는 명시적으로 매핑한 JSON-RPC와 설정한 버전을 지원하며 모든 MCP 기능 인증을 뜻하지 않습니다. 임의 MCP 전송, WebSocket 터널, 암호화 본문, 무제한 CONNECT, 자동 트래픽 발견은 범위 밖입니다. 마스킹은 허용된 필드·형식만 변경하며 안전하지 않은 변환은 차단합니다. 시그니처는 제한된 알려진 패턴 탐지이며 모든 지시 공격 방어를 보장하지 않습니다. SSE는 제한된 완성 스트림을 버퍼링하며 무제한 토큰 스트리밍이 아닙니다.

별도 mirror 수집기는 복사본을 받아 원본을 차단·수정할 수 없고 헤더만 있으면 커버리지가 불완전합니다. 콘솔의 Mirror는 동기 프록시 경로에서 본문을 변경하지 않고 관찰하지만 검사 통신 장애는 차단합니다. 두 방식을 배치·보고에서 구분해야 합니다. JSONL 검사 증거와 SQLite 감사는 원문·키를 제외하지만 수정 가능한 로컬 저장소이며 불변 보존 서비스가 아닙니다.

## 네트워크 프로파일

콘솔은 loopback과 digest가 고정된 amd64/arm64 Envoy 이미지를 사용합니다. macOS는 Docker Desktop 호스트 전달, Linux는 host networking을 사용합니다. NIC 목록은 물리 포트 개수가 아닌 OS 인터페이스입니다. 2-NIC 라우팅, 투명 브리지, 송출 NIC 고정, 실 IdP/TLS, HA, 운영 성능은 별도 작업입니다. 선택적 agentgateway 테스트는 호환성 검증이며 관리형 게이트웨이 서비스가 아닙니다.
