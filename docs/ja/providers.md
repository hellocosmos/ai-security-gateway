# モデル提供者への接続 (0.45)

[English](../en/providers.md) · [한국어](../ko/providers.md) · [简体中文](../zh-CN/providers.md) · [日本語](../ja/providers.md) · [Español](../es/providers.md) · [Français](../fr/providers.md)

既存 SDK と API 形式を維持し、base_url と api_key を変更します。SDK api_key にはゲートウェイ接続キー、または任意の個別エージェント認証情報を設定します。提供者の実キーはゲートウェイに保存します。

1 配備につき提供者は 1 つです。明示的なモデル許可リストと完全一致パスを使います。複数提供者には別の Compose プロジェクト、ポート、状態ボリュームを使います。

SSE は応答全体をバッファリングし、検査後に元のイベント形式で配信します。リアルタイム配信ではありません。既定は 120 秒、1 MiB。不完全または未対応の応答は遮断します。

テキストとクライアント側関数呼び出しに対応します。ファイル、メディア、提供者側ツール、WebSocket、暗号化推論、Gemini thought signature は対象外です。実ツール実行の制御には HTTP/MCP 経路も別途接続してください。

エージェント単位の制御には agent_key と Broker を有効にし、コンソールでツール権限と自律アクセスを登録してキーを発行します。同じ SDK api_key に設定します。

設定例は deploy/selfhost/providers/ にあります。YOUR_MODEL_ID を利用可能なモデル ID に置換し、提供者キーを /state/provider-key に安全に保存します。公式 Python SDK の合成検証であり、実サービスの全機能を保証しません。

| Provider | Gateway base_url | API |
| --- | --- | --- |
| OpenAI | https://gateway.example.com/v1 | Chat Completions / Responses |
| Anthropic | https://gateway.example.com | Messages |
| Gemini native | https://gateway.example.com | v1beta generateContent / streamGenerateContent |
| Gemini OpenAI | https://gateway.example.com/v1beta/openai | Chat Completions |
| OpenRouter | https://gateway.example.com/api/v1 | Chat Completions |


[SDK examples / Docker commands](../en/providers.md) · [AISG](aisg.md)

## 0.44 · Buffered SSE

[Buffered SSE の遅延と導入適合性](latency.md)

ゲートウェイは対応する応答全体を収集・検査してから内容を配信します。最初の内容までの遅延には収集と検査の両方が含まれます。完全な結果を待てる処理に適し、対話チャットは明確な遅延予算で評価する必要があります。
