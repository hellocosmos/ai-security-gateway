# 모델 → MCP → 모델 검증 (0.44)

[English](../en/agent-workflow.md) · [한국어](../ko/agent-workflow.md) · [简体中文](../zh-CN/agent-workflow.md) · [日本語](../ja/agent-workflow.md) · [Español](../es/agent-workflow.md) · [Français](../fr/agent-workflow.md)

독립된 두 Gateway를 통해 공식 OpenAI SDK와 MCP 클라이언트를 연결합니다. 모델 base_url뿐 아니라 MCP URL도 변경해야 실제 도구 실행을 통제할 수 있습니다. 같은 Agent ID를 사용하지만 두 Gateway의 키는 별개입니다.

기본 모드는 스크립트 기반 합성 모델입니다. 실제 추론이나 유료 호출이 아닙니다. 실제 Docker·Envoy·검사기 경로에서 Agent A 조회 허용, Agent B 조회 거부, 삭제 차단, PII 마스킹, 사용한 키 폐기 및 과거 시점으로 설정한 만료 키를 검증합니다. 차단 사유와 실제 목적지 실행 기록을 함께 확인합니다.

실제 OpenAI 검증에는 명시적인 모델 ID와 권한 0600의 테스트 키 파일이 필요합니다. --model과 --provider-key-file을 지정하면 합성 업무 데이터로 유료 API를 호출합니다. 실패 시 합성 모드로 대체하지 않습니다. 2026-09-18 실제 OpenAI `gpt-4.1-mini`로 세 시나리오를 각각 2회 모델 호출로 검증했습니다. MCP 대상과 업무 데이터는 합성입니다. 해당 모델·계정에서의 검증이며 전체 제공사나 운영 환경 인증은 아닙니다. LLM 응답 쿠키는 제거하고, Chat Completions·OpenAI Responses 및 지원 SSE의 정수형 생성 시각은 제한된 범위에서 프로토콜 메타데이터로 처리합니다. 중첩된 업무 필드는 계속 검사합니다.

자동 생성된 테스트 프로젝트만 정리합니다. 네트워크 경로와 Agent 권한을 검증하는 예제이며 서버 간 HA·운영 용량·실시간 스트리밍·즉시 생성 취소를 보장하지 않습니다. 전체 명령과 제한은 영문 가이드를 참고하세요.

```bash
pip install -e '.[dev,console,compat,llm-compat]'
python -m examples.agent_workflow --report .runtime-state/workflow-042.json
```

[Full setup / live mode / evidence](../en/agent-workflow.md)


## 0.42

추가 검증: 실제 로컬 MCP 서버의 문서 작업·차단·검사기 장애, 동일 서버 검사기 재시작·재전송 방지, 4개 제공사 SDK 합성 계약을 검사했습니다. 고객 MCP 및 타 제공사 실계정, 서버 간 HA 검증은 아닙니다. 사용자당 0.1 RPS를 가정한 5초 로컬 부하에서 10·30 RPS는 예상 결과와 일치했으나 50 RPS부터 503이 발생했습니다. 검사한 표본에서는 금지 삭제 실행과 PII 유출이 없었습니다. 실제 용량 보장이나 하드웨어 권장치가 아니며 상세 수치는 영어 문서를 참고하세요.

[Detailed qualification and measurements](../en/agent-workflow.md#042-extended-qualification)

SSE 추가 확인: 지연된 두 조각의 이메일을 합쳐 마스킹한 뒤 전체 응답을 전달했습니다. 클라이언트가 먼저 타임아웃되어도 합성 제공사는 생성을 완료했습니다. 즉시 상위 생성 취소를 보장하지 않습니다.
