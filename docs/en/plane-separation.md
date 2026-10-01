# Control/data plane separation (0.47)

[English](../en/plane-separation.md) · [한국어](../ko/plane-separation.md) · [简体中文](../zh-CN/plane-separation.md) · [日本語](../ja/plane-separation.md) · [Español](../es/plane-separation.md) · [Français](../fr/plane-separation.md)

**Guarantee:** when the console (control plane) stops, crashes or its database is locked or damaged, the data plane keeps enforcing its **last verified policy snapshot**. When inspection or evidence storage is unavailable, the data plane still fails closed. No request reaches the destination without an inspection verdict.

This is failure-domain separation on one Docker host. It is not multi-node HA.

## Services

| Compose service | Role | Listens | Holds |
|---|---|---|---|
| `app` | Control plane: console, policy publisher, CLI (`init`, `client-key`, `activate-config`) | 18080 (published) | `console.sqlite`, Ed25519 policy **signing** key (`control-keys` volume) |
| `dataplane` | Gateway, inspector (or inspector pool), evidence spool | 18084 (published), 18081 and 18085 (internal) | Policy **verification** key only (`policy-trust`, read-only), nonces, broker state |
| `envoy` | Private inspection proxy | 18082 (internal) | Generated configuration |

The data plane never opens `console.sqlite` and never reads `deployment.yaml`. Its policy and connection settings arrive only as a signed snapshot. Envoy starts after the data plane reports ready, not after the console.

## Policy snapshots

- Every applied policy, and every startup, publishes an immutable snapshot under `/state/policy/` (`history/` plus an atomically replaced `current.json`). Unchanged content is not republished.
- The data plane checks for a new snapshot every 0.25 seconds. It verifies the signature, format, schema and revision order. New requests use the new policy; in-flight requests keep the policy they started with.
- **Apply answers after enforcement.** The console's policy apply returns after the data plane, and every pooled inspector, reports the new revision, for up to 5 seconds. If no acknowledgement arrives, the policy is saved and `policy.dataplane_pending` is audited.
- A rejected snapshot never replaces the running policy. The rejection appears in Connections → data plane status and is audited as `dataplane.snapshot_rejected`.

| Rejection reason | Meaning |
|---|---|
| `policy_snapshot_signature_invalid` | Content changed after signing, or a different key signed it |
| `policy_snapshot_malformed` / `policy_snapshot_invalid` | Partial, unreadable or schema-invalid file |
| `policy_snapshot_revision_regressed` | Older than the running revision |
| `connection_changed_restart_required` | Routes, destination or authentication changed; restart the data plane |
| `policy_snapshot_missing` / `policy_trust_key_unavailable` | Nothing verifiable is available; at startup the data plane stays closed |

## Evidence

Decision records are appended to a per-process spool in `/state/dataplane/events/`, with `fsync` for each record. The console imports them into its database. It commits the events and the read position in one transaction, so a console restart neither loses nor duplicates records. Records produced while the console is down appear when it returns. The events and overview APIs import pending records before they answer.

If a record cannot be written in **inline** mode, that request fails closed. New requests are rejected with HTTP 503 `dataplane_unavailable` until storage is writable again. Mirror mode continues and reports the storage failure. The exact reason appears only in operator status, never in client responses.

## Failure behavior (verified)

| Fault | Behavior | Evidence |
|---|---|---|
| Console process killed | Allow and block decisions continue; evidence is imported after restart | `tests/runtime/test_plane_faults_runtime.py` F1 |
| `console.sqlite` exclusively locked | No added inspection delay | F2 (Docker) and `tests/test_plane_isolation.py` |
| `console.sqlite` damaged or deleted | Data plane unaffected | `tests/test_plane_isolation.py` |
| Snapshot tampered, partial, foreign key or older | Last known good kept; rejection audited | F4 (Docker) and unit tests |
| No snapshot at data-plane start | No request is served | F5 |
| Inspector worker killed | That request fails; worker is replaced | `test_selfhost_runtime.py` pool test |
| Envoy stopped | HTTP 503, no direct fallback | F10 |
| Evidence storage write fails (inline) | Request fails closed; admission closes until storage recovers | unit tests |

Run the Docker fault suite with `TD_FAULT_E2E=1 python -m pytest tests/runtime/test_plane_faults_runtime.py -q`.

## Operations

```bash
docker compose ps
docker compose logs --tail=100 app dataplane envoy
# Data-plane readiness and status (internal port, not published):
docker compose exec -T dataplane python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:18085/_trapdefense/status').read().decode())"
```

Activating staged connection settings requires stopping all three services. `activate-config` refuses to run while the console, the data plane or Envoy is running.

```bash
docker compose stop app dataplane envoy
docker compose run --rm app activate-config
docker compose up -d app dataplane envoy
```

Mount fixed destination credentials (`static_bearer` and `static_api_key`) into **both** `dataplane` (to use them) and `app` (activation validates them). Restart `dataplane` after rotation.

Backup: `state` and `generated` are essential. If `control-keys` or `policy-trust` is lost, the console creates a new key pair at its next start and republishes the snapshot.

## Upgrading from 0.46

1. Back up as described in [self-hosting](self-hosting.md) and stop the stack.
2. Update the source, then run `docker compose build app`.
3. Move private Compose overrides: published gateway port changes and target-secret mounts belong on `dataplane` (and secret mounts also on `app`).
4. Run `docker compose up -d`. The console publishes the first signed snapshot from the existing saved policy. The data plane waits for it and then becomes ready.

The image's default command, `serve`, runs both planes as separate supervised processes in one container. A console exit restarts only the console. A data-plane exit stops the container. Use the split Compose services for the isolation described above.

## Performance

Gateway first-content p95 in milliseconds, same synthetic benchmark and host as [latency](latency.md) (2026-10-01, Docker ARM64, 14 CPUs). Differences are within single-run variation. Burst, PII, size-limit, timeout and credential boundaries are unchanged. The separate console process adds about 110 MiB of memory (sampled peak: data plane 149.5 MiB and 85.6% CPU, console 109.4 MiB). [JSON](../evidence/latency-047-synthetic.json)

| Scenario · concurrency | 0.46 | 0.47 |
|---|---:|---:|
| short · 1 / 8 / 32 | 232 / 420 / 1253 | 224 / 430 / 1232 |
| long · 1 / 8 / 32 | 822 / 1164 / 3014 | 810 / 1183 / 3112 |

## Limits

- Single host. Approvals, agent registration and credential issuance need the console; existing approvals and credentials keep working while it is down.
- The signing key protects the snapshot channel only if write access to `policy-trust` and `control-keys` stays restricted. Anyone who can write both volumes can sign policy.
- Revision order is enforced while a data-plane process runs. After a restart, the data plane accepts the current signed snapshot.
- Broker state and local agent credentials remain shared files on the `state` volume.
