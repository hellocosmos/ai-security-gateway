# コントロールプレーン/データプレーンの分離（0.47）

[English](../en/plane-separation.md) · [한국어](../ko/plane-separation.md) · [简体中文](../zh-CN/plane-separation.md) · [日本語](../ja/plane-separation.md) · [Español](../es/plane-separation.md) · [Français](../fr/plane-separation.md)

**保証:** コンソール（コントロールプレーン）が停止・クラッシュしたり、そのデータベースがロック・破損したりしても、データプレーンは**最後に検証されたポリシースナップショット**を適用し続けます。検査や証跡の保存ができない場合、データプレーンは引き続きフェイルクローズします。検査判定のないリクエストが宛先に届くことはありません。

これは 1 台の Docker ホスト内での障害ドメイン分離であり、マルチノード HA ではありません。

## サービス

| Compose サービス | 役割 | 待ち受け | 保持するもの |
|---|---|---|---|
| `app` | コントロールプレーン: コンソール、ポリシー発行、CLI（`init`、`client-key`、`activate-config`） | 18080（公開） | `console.sqlite`、Ed25519 ポリシー**署名**鍵（`control-keys` ボリューム） |
| `dataplane` | ゲートウェイ、検査器（または検査器プール）、証跡 spool | 18084（公開）、18081 と 18085（内部） | ポリシー**検証**鍵のみ（`policy-trust`、読み取り専用）、nonce、broker 状態 |
| `envoy` | 非公開の検査プロキシ | 18082（内部） | 生成された設定 |

データプレーンは `console.sqlite` を開かず、`deployment.yaml` も読みません。ポリシーと接続設定は署名済みスナップショットとしてのみ届きます。Envoy はコンソールではなく、データプレーンが ready になった後に起動します。

## ポリシースナップショット

- ポリシーの適用時と起動時に、`/state/policy/` 以下へ不変のスナップショットを発行します（`history/` と、アトミックに置き換えられる `current.json`）。内容が変わらなければ再発行しません。
- データプレーンは 0.25 秒ごとに新しいスナップショットを確認し、署名・形式・スキーマ・リビジョン順序を検証します。新しいリクエストから新ポリシーを使い、処理中のリクエストは開始時のポリシーを保持します。
- **適用は、実際に適用されてから応答します。**コンソールのポリシー適用は、データプレーン（およびプールの全検査器）が新リビジョンを報告するまで最大 5 秒待ちます。確認が来なければポリシーは保存され、`policy.dataplane_pending` が監査記録されます。
- 拒否されたスナップショットが実行中のポリシーを置き換えることはありません。拒否は接続画面のデータプレーン状態に表示され、`dataplane.snapshot_rejected` として監査されます。

| 拒否理由 | 意味 |
|---|---|
| `policy_snapshot_signature_invalid` | 署名後に内容が変更された、または別の鍵で署名された |
| `policy_snapshot_malformed` / `policy_snapshot_invalid` | 途中で切れている、読めない、またはスキーマに合わないファイル |
| `policy_snapshot_revision_regressed` | 実行中のリビジョンより古い |
| `connection_changed_restart_required` | ルート・宛先・認証が変更された。データプレーンの再起動が必要 |
| `policy_snapshot_missing` / `policy_trust_key_unavailable` | 検証できるものがない。起動時はデータプレーンが閉じたままになる |

## 証跡

判定記録は `/state/dataplane/events/` 以下のプロセスごとの spool に、記録ごとに `fsync` して追記されます。コンソールはこれを自身のデータベースに取り込みます。イベントと読み取り位置を同じトランザクションでコミットするため、コンソールが再起動しても記録の欠落や重複は起きません。コンソール停止中に発生した記録は、復帰後に表示されます。イベント API と概要 API は、応答前に保留中の記録を取り込みます。

**inline** モードで記録を書き込めない場合、そのリクエストはフェイルクローズします。ストレージが書き込み可能に戻るまで、新しいリクエストは HTTP 503 `dataplane_unavailable` で拒否されます。mirror モードは動作を続け、保存失敗を報告します。詳しい理由は運用者向けの状態にのみ表示され、クライアントへの応答には含まれません。

## 障害時の動作（検証済み）

| 障害 | 動作 | 根拠 |
|---|---|---|
| コンソールプロセスの強制終了 | 許可・ブロック判定が継続し、再起動後に証跡を取り込む | `tests/runtime/test_plane_faults_runtime.py` F1 |
| `console.sqlite` の排他ロック | 検査遅延は増えない | F2（Docker）と `tests/test_plane_isolation.py` |
| `console.sqlite` の破損・削除 | データプレーンに影響なし | `tests/test_plane_isolation.py` |
| スナップショットの改ざん・欠損・別の鍵・旧リビジョン | 直前の有効なポリシーを維持し、拒否を監査 | F4（Docker）と単体テスト |
| データプレーン起動時にスナップショットがない | リクエストを一切処理しない | F5 |
| 検査器 worker の強制終了 | そのリクエストは失敗し、worker が置き換えられる | `test_selfhost_runtime.py` のプールテスト |
| Envoy の停止 | HTTP 503、直接のフォールバックなし | F10 |
| 証跡ストレージへの書き込み失敗（inline） | リクエストはフェイルクローズし、ストレージ復旧まで受け付けを停止 | 単体テスト |

Docker の障害注入テストは `TD_FAULT_E2E=1 python -m pytest tests/runtime/test_plane_faults_runtime.py -q` で実行します。

## 運用

```bash
docker compose ps
docker compose logs --tail=100 app dataplane envoy
# データプレーンの準備状態とステータス（内部ポート、外部非公開）:
docker compose exec -T dataplane python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:18085/_trapdefense/status').read().decode())"
```

ステージした接続設定を有効化するには、3 つのサービスをすべて停止する必要があります。コンソール、データプレーン、Envoy のいずれかが動作中だと `activate-config` は拒否されます。

```bash
docker compose stop app dataplane envoy
docker compose run --rm app activate-config
docker compose up -d app dataplane envoy
```

固定の宛先認証情報（`static_bearer`、`static_api_key`）は、`dataplane`（使用する側）と `app`（有効化時に検証する側）の**両方**にマウントします。ローテーション後は `dataplane` を再起動してください。

バックアップ: `state` と `generated` は必須です。`control-keys` や `policy-trust` を失った場合、コンソールは次回起動時に新しい鍵ペアを作成し、スナップショットを再発行します。

## 0.46 からのアップグレード

1. [セルフホスティング](self-hosting.md)の手順でバックアップし、スタックを停止します。
2. ソースを更新し、`docker compose build app` を実行します。
3. 非公開の Compose override を移します。ゲートウェイの公開ポートの変更と宛先シークレットのマウントは `dataplane` に置きます（シークレットのマウントは `app` にも置きます）。
4. `docker compose up -d` を実行します。コンソールが既存の保存済みポリシーから最初の署名済みスナップショットを発行し、データプレーンはそれを待ってから ready になります。

イメージの既定コマンド `serve` は、1 つのコンテナ内で両プレーンを別々の監視付きプロセスとして実行します。コンソールが終了した場合はコンソールだけを再起動し、データプレーンが終了した場合はコンテナが停止します。上記の分離が必要な場合は、分割された Compose サービスを使ってください。

## 性能

ゲートウェイの最初のコンテンツまでの p95（ミリ秒）です。[レイテンシ](latency.md)と同じ合成ベンチマーク・同じホストで測定しました（2026-10-01、Docker ARM64、14 CPU）。差は 1 回の実行のばらつきの範囲内です。バースト、PII、サイズ上限、タイムアウト、認証情報の境界は変わっていません。コンソールが別プロセスになったことで、メモリが約 110 MiB 増えます（サンプル上の最大値: データプレーン 149.5 MiB・CPU 85.6%、コンソール 109.4 MiB）。[JSON](../evidence/latency-047-synthetic.json)

| シナリオ · 同時実行数 | 0.46 | 0.47 |
|---|---:|---:|
| short · 1 / 8 / 32 | 232 / 420 / 1253 | 224 / 430 / 1232 |
| long · 1 / 8 / 32 | 822 / 1164 / 3014 | 810 / 1183 / 3112 |

## 制限事項

- 単一ホストです。承認、エージェント登録、認証情報の発行にはコンソールが必要です。発行済みの承認と認証情報は、コンソール停止中も機能し続けます。
- 署名鍵がスナップショット経路を保護できるのは、`policy-trust` と `control-keys` への書き込み権限が制限されている場合に限られます。両方のボリュームに書き込める主体はポリシーに署名できます。
- リビジョン順序は、データプレーンのプロセスが動作している間だけ強制されます。再起動後は、現在の署名済みスナップショットを受け入れます。
- Broker 状態とローカルのエージェント認証情報は、引き続き `state` ボリューム上の共有ファイルです。
