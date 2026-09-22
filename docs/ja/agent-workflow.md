# モデル → MCP → モデルの検証 (0.44)

[English](../en/agent-workflow.md) · [한국어](../ko/agent-workflow.md) · [简体中文](../zh-CN/agent-workflow.md) · [日本語](../ja/agent-workflow.md) · [Español](../es/agent-workflow.md) · [Français](../fr/agent-workflow.md)

公式 OpenAI SDK と MCP クライアントを独立した2つの Gateway に接続します。モデルの base_url に加え、MCP URL も変更する必要があります。同じ Agent ID でも各 Gateway のキーは別です。

既定ではスクリプトによる合成モデルを使い、実際の推論や有料呼び出しは行いません。実際の Docker・Envoy・検査器で Agent A の読み取り許可、Agent B の拒否、削除の遮断、PII マスキング、使用済みキーの失効、過去に期限を設定した認証情報を検証します。判定理由と宛先の実行記録を照合します。

実際の OpenAI 検証にはモデル ID と権限 0600 のテストキーファイルが必要です。--model と --provider-key-file の指定で合成業務データを用いた有料 API 呼び出しを行います。失敗時に合成結果へ切り替えません。2026-09-18 に実際の OpenAI `gpt-4.1-mini` で3シナリオを検証し、各シナリオでモデルを2回呼び出しました。MCP 宛先と業務データは合成です。このモデル・アカウントでの検証であり、全プロバイダーや本番環境の認証ではありません。LLM 応答 Cookie は削除し、Chat Completions・OpenAI Responses・対応 SSE の範囲制限付き整数生成時刻 はプロトコルの時刻情報として扱います。入れ子の業務フィールドは引き続き検査します。

自動作成したテストプロジェクトのみ削除します。HA・性能・リアルタイム配信・キャンセルは検証対象外です。全コマンドと制限は英語ガイドを参照してください。

```bash
pip install -e '.[dev,console,compat,llm-compat]'
python -m examples.agent_workflow --report .runtime-state/workflow-042.json
```

[Full setup / live mode / evidence](../en/agent-workflow.md)


## 0.42

追加検証では実際のローカル MCP サーバーの文書操作・検査器障害、同一ホストの復旧・リプレイ防止、4社の SDK 合成契約を確認しました。顧客 MCP、他社の実アカウント、ホスト間 HA の認証ではありません。1ユーザー 0.1 RPS の5秒間ローカル試験では10・30 RPSが期待どおりでしたが、50 RPSから503が発生しました。試験標本では禁止された削除や PII 漏えいはありませんでした。容量保証や推奨ハードウェアではなく、詳細は英語版を参照してください。

[Detailed qualification and measurements](../en/agent-workflow.md#042-extended-qualification)

SSE 追加検証：遅延した2チャンクのメールアドレスを結合・マスクしてから応答を配信しました。クライアントのタイムアウト後も合成プロバイダーは生成を完了し、上流生成の即時キャンセルは保証しません。
