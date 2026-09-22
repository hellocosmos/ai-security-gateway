# TrapDefense — Open-source AI Security Gateway

[0.46: 제한된 진입 대기와 검사기 용량]](docs/ko/latency.md) · [대화형 스트리밍 판단](docs/ko/interactive-streaming.md)

[0.44: Buffered SSE 지연과 도입 적합성](docs/ko/latency.md)

## Least Privilege, Least Agency

**최소권한은 접근을 제한하고, 최소 자율성은 독자적인 행동의 범위를 제한합니다.**

우리의 설계 원칙은 에이전트에 필요한 접근만 부여하고 스스로 수행할 수 있는 행동의 범위를 정하는 것입니다. TrapDefense는 기존 IAM과 대상 서비스 권한을 보완하며, 게이트웨이로 라우팅된 지원 호출에 작업·데이터 정책을 집행합니다. 선택적 에이전트 신원은 에이전트별 권한 범위·위임·승인 통제를 추가합니다.

[0.44: 운영 작업 공간 (0.44)](docs/ko/operator-workspace.md)


[0.42: 모델 → MCP → 모델 검증](docs/ko/agent-workflow.md)

**0.44:** [모델 제공자 연결](docs/ko/providers.md) — OpenAI · Anthropic · Gemini · OpenRouter.

**지원되는 HTTP API와 원격 MCP 서버를 명시적인 보안 경로로 연결합니다. 에이전트별 통제가 필요하면 신원을 추가합니다.**

[연결 → 신원 → 통제 → 확인 →](docs/ko/aisg.md)

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Français](README.fr.md)

> **Open Source Preview 0.46:** 전체 런타임과 운영 UI는 MIT 라이선스다. 내장 Agent Access Broker는 구현과 합성 검증을 마쳤지만, 실제 IdP·고객 정책·HA·용량 검증 전까지 **Experimental**로 표시한다.

TrapDefense는 지원되는 HTTP 및 MCP 트래픽을 위한 셀프호스팅 AI Firewall이다. 요청과 응답을 검사하고, action/PII/secret 정책을 집행하며, 정제된 증거를 저장한다. 선택적으로 등록된 agent, delegation, task, resource, action, 일회성 human approval을 함께 평가한다.

```text
AI agent → 인증 gateway → trusted request binding → Envoy + inspector
         → 선택적 내장 Access Broker → Tool / MCP / HTTP API
```

## 콘솔 화면

합성 데이터를 사용한 실제 0.41 화면입니다. 대시보드에는 의도적인 7초 제공사 지연 테스트가 포함되어 있어 성능 벤치마크가 아닙니다. Agent 관리는 별도의 로컬 데모 화면입니다.

![런타임 대시보드](docs/assets/console-dashboard-041.png)

<table>
<tr>
<td width="50%"><img src="docs/assets/console-agents-041.png" alt="Agent 권한 · 실험적 기능"><br><strong>Agent 권한 · 실험적 기능</strong></td>
<td width="50%"><img src="docs/assets/console-provider-041.png" alt="제공사 연결 설정"><br><strong>제공사 연결 설정</strong></td>
</tr>
</table>

## 하나의 오픈소스 제품

Community/Enterprise 코드 에디션을 구분하지 않는다. Runtime Gateway, HTTP/MCP 검사, PII/secret 보호, 외부 OAuth JWT 검증, Agent Registry, delegation, Access Broker, human approval, audit, 운영 콘솔과 Docker 셀프호스팅이 모두 이 공개 저장소에 있다. 실행 시 비공개 패키지는 필요하지 않다.

향후 유료 범위는 managed cloud, fleet 운영, multi-node HA, 외부 immutable audit, 고객별 연동과 지원이 될 수 있다. 현재 오픈소스 집행 기능을 라이선스로 잠그는 구조는 아니다. [오픈소스 모델](docs/ko/editions.md)

## Docker 셀프호스팅

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
```

`http://localhost:18080`에서 초기화 때 지정한 admin 비밀번호로 로그인한다. 클라이언트는 HTTP/MCP URL과 `X-TD-Client-Key` 또는 Bearer JWT를 설정할 수 있어야 한다. 대상 서비스 credential은 별도이며, 한 설치는 하나의 고정 destination과 명시적 route/tool mapping을 사용한다. [셀프호스팅 계약](docs/ko/self-hosting.md)

## 내장 Access Broker (Experimental)

Gateway-only 모드는 forwarding source와 로컬 검사 정책을 검증하며 agent identity를 주장하지 않는다. Broker 모드는 외부 IdP가 발급한 JWT와 명시적 claim mapping을 요구한다. TrapDefense는 검증된 claim 중 설정된 항목만 `tenant_id`, `user_id`, `agent_id`, `delegation_id`, `task_id` 등으로 정규화한다. 필수 identity가 빠지면 전달 전에 차단한다.

Broker는 tenant, registry, tool/resource scope, delegation, user, task, action, request digest와 approval을 검사한다. 고위험 action은 `approval_required`가 되고, 승인된 요청은 정확히 한 번만 사용할 수 있다. TrapDefense는 대상 서비스의 권한 체계를 대체하지 않으며 downstream OAuth token을 발급하지 않는다.

## 소스 데모와 검증

```bash
./scripts/install-console.sh
./scripts/run-console.sh
```

[http://127.0.0.1:5176](http://127.0.0.1:5176)에서 `admin` / `1234`로 로그인한 뒤 비밀번호를 변경한다. 데모는 실제 파일 기반 Broker에 합성 agent/delegation을 등록하며, 배포 시나리오에서 `승인 필요 → 승인 → 1회 실행 → 재사용 차단`을 보여준다.

```bash
pip install -e ".[dev]"
pytest -q
npm run check --prefix console
npm run build --prefix console
```

이 결과는 소스·프로토콜·합성 검증 증거다. 실제 Entra/Okta/Keycloak tenant, Conditional Access, 고객 MCP 인증, 우회 방지 라우팅, HA와 운영 용량을 증명하지는 않는다.

[콘솔](docs/ko/console.md) · [아키텍처](docs/ko/architecture.md) · [보안](docs/ko/security.md) · [마이그레이션](docs/ko/migration.md) · [영문 기준 문서](README.md)

## 라이선스

MIT. 이 저장소의 Runtime Gateway와 Access Broker 전체가 오픈소스다.
