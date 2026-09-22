# Docker セルフホスティング — 0.44 Open Source Preview

> **0.44:** [運用ワークスペース（0.44）](operator-workspace.md)


> [モデル提供者への接続](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [接続・識別・制御・検証](aisg.md). ゲートウェイは接続キーまたは検証済みJWTを使用します。agent_keyは外部IAMなしで登録済みエージェントを識別します。JWT identity_mode: agentは検証済みテナントとエージェントのクレームを使用し、delegatedはユーザー・タスク・委任も要求します。既存エージェントは既定で委任が必要です。

[English](../en/self-hosting.md) · [한국어](../ko/self-hosting.md) · [简体中文](../zh-CN/self-hosting.md) · [日本語](../ja/self-hosting.md) · [Español](../es/self-hosting.md) · [Français](../fr/self-hosting.md)

## 0.44 の開始方法を選ぶ

- **モデル API：**[プロバイダー設定](providers.md)で OpenAI・Anthropic・Gemini・OpenRouter に接続します。SDK base URL を変更し、プロバイダーキーはゲートウェイに保存します。
- **HTTP / MCP ツール：**以下の Docker サンプルから始め、合成宛先を明示的にマッピングしたサービスに変更します。
- **全体検証：**[2エージェントのモデル → MCP → モデル例](agent-workflow.md)を実行します。既定では有料キー不要です。実 OpenAI の証拠、合成試験、測定上の限界を区別しています。

ゲートウェイ認証は `client_key`・`agent_key`・外部 `jwt` に対応します。ローカル Agent Registry と agent_key の権限制御は任意で、宛先認証を置き換えません。導入ごとに宛先は1つです。モデルと別途実行するツールはそれぞれ経路設定が必要です。モデル SSE は全体をバッファして検査後に配信し、リアルタイムのトークン配信ではありません。

0.44 はアダプター、Envoy、検査器、管理 UI と、分離したゲートウェイ/宛先認証を提供します。イメージはソースからローカルでビルドします。TrapDefense Cloud は計画段階です。

クライアントは MCP/API URL を変更し、`X-TD-Client-Key` または OAuth Bearer JWT を使用できる必要があります。導入ごとに宛先を一つに固定し、ルートとツールを明示します。証拠は[互換性表](gateway-compatibility.md)を参照してください。

| 種別 | 対応範囲 |
|---|---|
| HTTP API | JSON、正確な method/path、最大 1 MiB、有限の応答 |
| MCP | ステートレス JSON POST、明示した制御メソッドとツール |
| ゲートウェイ認証 | 接続キー、または外部 IdP の RS256 JWT（issuer/audience/scope と RFC 9728 metadata） |
| 宛先認証 | none、旧式 Bearer 転送、ファイルベースの固定 Bearer/API Key |
| 未対応 | OAuth 発行・ログイン仲介・DCR・OBO、Cookie/セッション、長時間 SSE、WebSocket、stdio、閉鎖型 SaaS 内部呼び出し |

管理者パスワードはコンソール用です。接続キーまたは JWT は TrapDefense へのアクセス用です。JWT は設定した gateway audience に対して検証され、宛先へ転送されません。宛先サービスは別の資格情報で権限を確認します。接続キーや JWT だけでエージェントを自動登録しません。登録と権限は任意の Access Broker で別途管理し、OAuth 発行は外部 IdP が担当します。

## Docker

Git と Docker Compose v2 が必要です。init で 12 文字以上の管理者パスワードを設定します。既定のパスワードはありません。サンプルは合成宛先であり、実サービス連携の証明ではありません。

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
docker compose run --rm app client-key
```

http://localhost:18080 で admin としてログインします。client-key で接続キーを確認し、クライアントの秘密ヘッダー設定に保存します。ゲートウェイは http://localhost:18084、合成宛先のトークンは Bearer synthetic-target-token です。

実際の接続では deployment.yaml の upstream、authority、パス、ツール、resource を変更します。`gateway_auth` は `client_key`、`agent_key` または `jwt`、`target_auth` は `none`、`passthrough_bearer`、`static_bearer`、`static_api_key` を使います。JWT と passthrough は併用できません。固定資格情報は UID 10001 が読める 0600 ファイルでマウントし、競合する入力を拒否します。

UI はポリシーとパスワードを管理します。マッピング変更時はバックアップ後に policy-reset、render、スタック再作成を行います。保存済みポリシーのみリセットし、アカウント・キー・イベントは保持します。新しい要求に新ポリシーが適用されます。

既定の公開アドレスはループバックです。遠隔利用には TLS プロキシと正確な console_origin が必要です。検査器と Envoy のホストポートは公開されません。経路迂回は顧客ネットワークで防止してください。

再起動しても名前付きボリュームの状態は保持されます。停止後に両ボリュームと設定をバックアップします。down -v はデータを削除します。ロールバックは旧イメージと対応するバックアップを復元します。リスナーの正常性だけでなく、許可・拒否要求と宛先の動作を確認してください。長時間ストリーム、HA、実顧客 IAM は別途検証が必要です。

[互換性と VS Code](gateway-compatibility.md) · [Detailed examples, backup and migration (English)](../en/self-hosting.md)

## 内蔵 Access Broker の有効化

以下は **delegated JWT モード**の設定です。ローカル agent_key と自律 agent モードは [AISG ガイド](aisg.md)を参照してください。

`gateway_auth.mode: jwt` を使い、`identity_claims` に tenant、user、agent、delegation、task の claim 名を明示します。次に `access_broker.enabled: true` と 1 つの `access_broker.tenant_id` を設定します。同じ tenant の agent と delegation をコンソールで事前登録してください。必須 claim の欠落や tenant 不一致は転送前に拒否されます。正確な YAML は[英語基準文書](../en/self-hosting.md)を参照してください。ローカル file store は同一ホスト向けで、multi-node HA ではありません。

## 0.44 · Buffered SSE

[Buffered SSE の遅延と導入適合性](latency.md)

ゲートウェイは対応する応答全体を収集・検査してから内容を配信します。最初の内容までの遅延には収集と検査の両方が含まれます。完全な結果を待てる処理に適し、対話チャットは明確な遅延予算で評価する必要があります。
