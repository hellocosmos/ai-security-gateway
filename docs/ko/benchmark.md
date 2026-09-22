# 로컬 성능 기준선

[English](../en/benchmark.md) · [한국어](../ko/benchmark.md) · [简体中文](../zh-CN/benchmark.md) · [日本語](../ja/benchmark.md) · [Español](../es/benchmark.md) · [Français](../fr/benchmark.md)

이 명령은 설치된 Envoy 리스너, gRPC ExtProc 검사기, 합성 HTTP 목적지를 통과하는 **합성 로컬 기준선**을 측정합니다. 같은 호스트에서 리비전 간 회귀를 비교하기 위한 것으로 운영 용량·HA·고객 트래픽 인증이 아닙니다.

## 실행

`./scripts/install-console.sh`로 한 번 설치하고, 벤치마크가 같은 loopback 포트를 사용하므로 실행 중인 콘솔을 중지합니다.

```bash
.venv/bin/trapdefense-benchmark --scenario read --iterations 30
```

시나리오는 `read`, `pii`, `secret`, `response`입니다. 반복 횟수는 5–500, 워밍업은 0–50으로 제한하며 기본값은 워밍업 3회 뒤 30회 측정입니다. 각 요청은 실제 프록시 경로를 통과하고 정제된 판단 증거를 생성합니다. 외부 업무 목적지나 모델 API는 사용하지 않습니다.

## JSON 해석

`p50_ms`, `p95_ms`, `mean_ms`, `sequential_requests_per_second`는 로컬 회귀 기준으로만 사용합니다. 판단과 HTTP 상태 개수로 예상 정책 결과가 측정 중 바뀌지 않았는지 확인합니다. OS·아키텍처·Python·논리 CPU 수는 기록하지만 호스트명과 검사 내용은 제외합니다.

호스트 부하, Docker 버전, 전원 모드, 시나리오, 반복 횟수, 정책이 같을 때만 비교하세요. 최소 세 번 실행하고 중앙 결과를 보관하는 것이 좋습니다. 병렬 용량, 연결 재사용, 대형 본문, 장시간 SSE, 장애 복구, 다중 노드는 별도 벤치마크가 필요합니다.

[콘솔 안내](console.md), [아키텍처](architecture.md), [에디션](editions.md), [보안 범위](security.md)를 참고하세요.

## AI Firewall 검사기 다중 프로세스

[AI Firewall 검사기 다중 프로세스](inspector-pool.md)

## 0.44 · Buffered SSE

[Buffered SSE 지연과 도입 적합성](latency.md)

게이트웨이는 지원되는 응답 전체를 수집·검사한 뒤 콘텐츠를 전달합니다. 첫 콘텐츠 지연에는 검사뿐 아니라 응답 수집도 포함됩니다. 완성된 결과를 기다릴 수 있는 작업에 적합하며, 대화형 채팅은 명시적인 지연 예산으로 평가해야 합니다.
