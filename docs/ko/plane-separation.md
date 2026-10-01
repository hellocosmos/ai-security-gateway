# Control/Data plane 분리 (0.47)

[English](../en/plane-separation.md) · [한국어](../ko/plane-separation.md) · [简体中文](../zh-CN/plane-separation.md) · [日本語](../ja/plane-separation.md) · [Español](../es/plane-separation.md) · [Français](../fr/plane-separation.md)

**보장:** 콘솔(control plane)이 중지·충돌하거나 그 데이터베이스가 잠기거나 손상돼도, data plane은 **마지막으로 검증된 정책 스냅샷**을 계속 집행한다. 검사나 증거 저장이 불가능하면 data plane은 여전히 fail-closed로 동작한다. 검사 판정 없이 목적지에 도달하는 요청은 없다.

이것은 단일 Docker 호스트 안의 장애 도메인 분리이며, 다중 노드 HA가 아니다.

## 서비스

| Compose 서비스 | 역할 | 리스너 | 보유 자산 |
|---|---|---|---|
| `app` | Control plane: 콘솔, 정책 발행, CLI(`init`, `client-key`, `activate-config`) | 18080 (공개) | `console.sqlite`, Ed25519 정책 **서명** 키(`control-keys` 볼륨) |
| `dataplane` | 게이트웨이, inspector(또는 inspector 풀), 증거 spool | 18084 (공개), 18081·18085 (내부) | 정책 **검증** 키만(`policy-trust`, 읽기 전용), nonce, broker 상태 |
| `envoy` | 비공개 검사 프록시 | 18082 (내부) | 생성된 설정 |

data plane은 `console.sqlite`를 열지 않고 `deployment.yaml`도 읽지 않는다. 정책과 연결 설정은 서명된 스냅샷으로만 전달된다. Envoy는 콘솔이 아니라 data plane이 ready가 된 뒤 시작한다.

## 정책 스냅샷

- 정책을 적용할 때와 기동할 때마다 `/state/policy/` 아래에 불변 스냅샷이 발행된다(`history/`와 원자적으로 교체되는 `current.json`). 내용이 같으면 다시 발행하지 않는다.
- data plane은 0.25초마다 새 스냅샷을 확인한다. 서명, 형식, 스키마, revision 순서를 검증한다. 새 요청부터 새 정책을 쓰고, 진행 중인 요청은 시작할 때의 정책을 유지한다.
- **적용은 집행 이후에 응답한다.** 콘솔의 정책 적용은 data plane(풀 모드에서는 모든 inspector)이 새 revision을 보고할 때까지 최대 5초 기다린 뒤 응답한다. 확인이 오지 않으면 정책은 저장되고 `policy.dataplane_pending`이 감사 로그에 남는다.
- 거부된 스냅샷은 실행 중인 정책을 대체하지 않는다. 거부 사실은 연결 화면의 data plane 상태에 표시되고 `dataplane.snapshot_rejected`로 감사된다.

| 거부 사유 | 의미 |
|---|---|
| `policy_snapshot_signature_invalid` | 서명 후 내용이 바뀌었거나 다른 키로 서명됨 |
| `policy_snapshot_malformed` / `policy_snapshot_invalid` | 잘렸거나 읽을 수 없거나 스키마가 틀린 파일 |
| `policy_snapshot_revision_regressed` | 실행 중인 revision보다 오래됨 |
| `connection_changed_restart_required` | 라우트·목적지·인증이 바뀜. data plane을 재시작해야 함 |
| `policy_snapshot_missing` / `policy_trust_key_unavailable` | 검증 가능한 것이 없음. 기동 시에는 data plane이 닫힌 상태로 유지됨 |

## 증거

판정 기록은 `/state/dataplane/events/` 아래 프로세스별 spool에 기록마다 `fsync`로 추가된다. 콘솔이 이를 자신의 DB로 가져온다. 이벤트와 읽은 위치를 한 트랜잭션으로 커밋하므로 콘솔이 재시작해도 기록이 사라지거나 중복되지 않는다. 콘솔이 내려가 있던 동안의 기록은 콘솔이 돌아오면 나타난다. 이벤트·개요 API는 응답 전에 대기 중인 기록을 먼저 가져온다.

**inline** 모드에서 기록을 쓸 수 없으면 해당 요청은 fail-closed로 실패한다. 저장소가 다시 쓰기 가능해질 때까지 새 요청은 HTTP 503 `dataplane_unavailable`로 거부된다. mirror 모드는 계속 동작하면서 저장 실패를 보고한다. 정확한 사유는 운영자 상태에만 나오고, 클라이언트 응답에는 나오지 않는다.

## 장애 동작 (검증됨)

| 장애 | 동작 | 근거 |
|---|---|---|
| 콘솔 프로세스 강제 종료 | 허용·차단 판정이 계속되고, 재시작 후 증거를 가져옴 | `tests/runtime/test_plane_faults_runtime.py` F1 |
| `console.sqlite` 배타 잠금 | 검사 지연이 추가되지 않음 | F2(Docker), `tests/test_plane_isolation.py` |
| `console.sqlite` 손상·삭제 | data plane 영향 없음 | `tests/test_plane_isolation.py` |
| 스냅샷 변조·잘림·다른 키·이전 revision | 마지막 정상 정책 유지, 거부 감사 | F4(Docker), 단위 테스트 |
| data plane 기동 시 스냅샷 없음 | 어떤 요청도 처리하지 않음 | F5 |
| inspector worker 강제 종료 | 해당 요청은 실패하고 worker가 교체됨 | `test_selfhost_runtime.py` 풀 테스트 |
| Envoy 중지 | HTTP 503, 직접 우회 없음 | F10 |
| 증거 저장 실패(inline) | 요청 fail-closed, 저장소 복구 전까지 입장 차단 | 단위 테스트 |

Docker 장애 주입 묶음은 `TD_FAULT_E2E=1 python -m pytest tests/runtime/test_plane_faults_runtime.py -q`로 실행한다.

## 운영

```bash
docker compose ps
docker compose logs --tail=100 app dataplane envoy
# data plane 준비 상태와 상태 정보(내부 포트, 외부 공개 안 됨):
docker compose exec -T dataplane python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:18085/_trapdefense/status').read().decode())"
```

스테이징한 연결 설정을 활성화하려면 세 서비스를 모두 중지해야 한다. 콘솔, data plane, Envoy 중 하나라도 실행 중이면 `activate-config`는 거부된다.

```bash
docker compose stop app dataplane envoy
docker compose run --rm app activate-config
docker compose up -d app dataplane envoy
```

고정 목적지 자격 증명(`static_bearer`, `static_api_key`)은 **두 곳 모두**에 마운트한다. `dataplane`은 이를 사용하고, `app`은 활성화할 때 검증한다. 교체한 뒤에는 `dataplane`을 재시작한다.

백업: `state`와 `generated`는 필수다. `control-keys`나 `policy-trust`를 잃으면 콘솔이 다음 기동 때 새 키 쌍을 만들고 스냅샷을 다시 발행한다.

## 0.46에서 업그레이드

1. [셀프호스팅](self-hosting.md)에 따라 백업하고 스택을 중지한다.
2. 소스를 갱신한 뒤 `docker compose build app`을 실행한다.
3. 비공개 Compose override를 옮긴다. 게이트웨이 공개 포트 변경과 목적지 시크릿 마운트는 `dataplane`에 둔다(시크릿 마운트는 `app`에도 둔다).
4. `docker compose up -d`를 실행한다. 콘솔이 기존 저장 정책으로 첫 서명 스냅샷을 발행한다. data plane은 이를 기다렸다가 ready가 된다.

이미지 기본 명령 `serve`는 한 컨테이너 안에서 두 plane을 별도의 감독 프로세스로 실행한다. 콘솔이 종료되면 콘솔만 재시작하고, data plane이 종료되면 컨테이너가 종료된다. 위에서 설명한 격리를 원하면 분리된 Compose 서비스를 사용한다.

## 성능

게이트웨이 first-content p95(밀리초)입니다. [지연](latency.md)과 같은 합성 벤치마크, 같은 호스트에서 측정했습니다(2026-10-01, Docker ARM64, CPU 14개). 차이는 단일 실행의 변동 범위 안에 있습니다. 버스트, PII, 크기 제한, 타임아웃, 자격 증명 경계는 변하지 않았습니다. 콘솔이 별도 프로세스가 되면서 메모리가 약 110 MiB 늘었습니다(샘플 최댓값: data plane 149.5 MiB·CPU 85.6%, 콘솔 109.4 MiB). [JSON](../evidence/latency-047-synthetic.json)

| 시나리오 · 동시성 | 0.46 | 0.47 |
|---|---:|---:|
| short · 1 / 8 / 32 | 232 / 420 / 1253 | 224 / 430 / 1232 |
| long · 1 / 8 / 32 | 822 / 1164 / 3014 | 810 / 1183 / 3112 |

## 한계

- 단일 호스트다. 승인, 에이전트 등록, 자격 증명 발급에는 콘솔이 필요하다. 이미 발급된 승인과 자격 증명은 콘솔이 내려가 있어도 계속 동작한다.
- 서명 키는 `policy-trust`와 `control-keys`의 쓰기 권한이 제한될 때만 스냅샷 경로를 보호한다. 두 볼륨에 모두 쓸 수 있는 주체는 정책에 서명할 수 있다.
- revision 순서는 data plane 프로세스가 실행되는 동안 강제된다. 재시작 후에는 현재의 서명된 스냅샷을 수용한다.
- Broker 상태와 로컬 에이전트 자격 증명은 여전히 `state` 볼륨의 공유 파일이다.
