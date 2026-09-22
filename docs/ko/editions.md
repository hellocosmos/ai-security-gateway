# 하나의 오픈소스 제품

> **AISG:** [연결 → 신원 → 통제 → 확인](aisg.md). Gateway 접속은 연결 키 또는 검증된 JWT로 인증합니다. 로컬 agent_key는 외부 IAM 없이 등록된 에이전트를 식별합니다. JWT identity_mode: agent는 검증된 테넌트·에이전트 정보를 사용하고, delegated는 사용자·작업·위임도 요구합니다. 기존 에이전트는 기본적으로 위임이 필요합니다.

[English](../en/editions.md) · [한국어](../ko/editions.md) · [简体中文](../zh-CN/editions.md) · [日本語](../ja/editions.md) · [Español](../es/editions.md) · [Français](../fr/editions.md)

TrapDefense 0.44는 하나의 MIT 코드베이스다. Runtime Gateway와 Agent Access Broker를 이 공개 저장소에서 함께 제공하며, 비공개 Python 배포판·provider entry point·license key·edition switch가 필요하지 않다.

## 제공 상태

| 경계 | 상태 | 증거와 한계 |
|---|---|---|
| Runtime Gateway와 콘솔 | **Open Source Preview** | 공개 소스, CI, 합성 Envoy 경로, HTTP/MCP 정책, PII/secret 통제, 로컬 UI를 제공한다. 실제 라우팅과 용량은 환경별 검증이 필요하다. |
| 내장 Agent Access Broker | **Experimental** | 공개 registry, delegation, strict authorization, tenant isolation, file transaction, 요청 결합 일회성 승인을 구현했다. 실제 고객 IdP/정책과 multi-node 검증은 남아 있다. |
| Docker 셀프호스팅 | **Preview** | adapter, Envoy, inspector, console, gateway 인증과 별도 target credential을 소스에서 빌드한다. 설치당 고정 destination 하나를 사용한다. |
| Managed cloud, fleet, multi-node HA, 외부 immutable audit | **Planned** | 현재 제공하지 않으며 사용 가능한 기능으로 표현하지 않는다. |

Gateway-only는 로컬 검사 정책과 trusted source를 검증한다. Broker-enabled는 검증된 JWT identity mapping, agent registry, delegation, resource/action 인가와 approval을 더한다. 두 모드 모두 같은 오픈소스 패키지다.

향후 유료 제품은 동일 오픈소스 런타임의 managed service, fleet lifecycle, multi-node HA, 외부 audit, 고객 connector, 정책 온보딩, SLA와 지원이 될 수 있다. 이것은 서비스·운영 경계이지 소스 기능 제한이 아니다.

파일 store는 동일 호스트 POSIX 프로세스에서 atomic replace와 file lock을 사용한다. 분산 DB가 아니며 NFS/SMB multi-host HA 용도가 아니다. 로컬 JSON/SQLite 증거는 변경 가능하다. 합성 테스트는 실제 IdP, Conditional Access, 고객 MCP 인증, TLS 라우팅과 용량을 인증하지 않는다.

[Docker 0.44](self-hosting.md) · [아키텍처](architecture.md) · [보안](security.md) · [호환성](gateway-compatibility.md)
