# ローカル性能ベースライン

[English](../en/benchmark.md) · [한국어](../ko/benchmark.md) · [简体中文](../zh-CN/benchmark.md) · [日本語](../ja/benchmark.md) · [Español](../es/benchmark.md) · [Français](../fr/benchmark.md)

このコマンドは、インストール済みの Envoy リスナー、gRPC ExtProc 検査器、合成 HTTP 宛先を通る再現可能な**合成ローカルベースライン**を測定します。同じホストでリビジョン間の回帰を比較するためのもので、本番容量、HA、顧客通信の認証ではありません。

## 実行

`./scripts/install-console.sh` で一度インストールし、同じループバックポートを使うため実行中のコンソールを停止します。

```bash
.venv/bin/trapdefense-benchmark --scenario read --iterations 30
```

シナリオは `read`、`pii`、`secret`、`response` です。反復は 5–500、ウォームアップは 0–50 に制限され、既定値は 3 回のウォームアップ後に 30 回測定します。各要求はプロキシを通過してサニタイズ済み証跡を生成し、外部業務宛先やモデル API は使いません。

## JSON の解釈

`p50_ms`、`p95_ms`、`mean_ms`、`sequential_requests_per_second` はローカル回帰の参照にのみ使用します。判断と HTTP ステータスの件数により、期待結果が測定中に変わっていないことを確認できます。OS、アーキテクチャ、Python、論理 CPU 数は含みますが、ホスト名と検査内容は除外します。

ホスト負荷、Docker、電源モード、シナリオ、反復数、ポリシーが同じ場合にのみ比較してください。最低 3 回実行して中央値の結果を保持します。並列容量、接続再利用、大きな本文、長時間 SSE、障害復旧、複数ノードは別の測定が必要です。

[コンソール](console.md)、[アーキテクチャ](architecture.md)、[エディション](editions.md)、[セキュリティ](security.md)を参照してください。

## AI Firewall インスペクタープール

[AI Firewall インスペクタープール](inspector-pool.md)

## 0.44 · Buffered SSE

[Buffered SSE の遅延と導入適合性](latency.md)

ゲートウェイは対応する応答全体を収集・検査してから内容を配信します。最初の内容までの遅延には収集と検査の両方が含まれます。完全な結果を待てる処理に適し、対話チャットは明確な遅延予算で評価する必要があります。
