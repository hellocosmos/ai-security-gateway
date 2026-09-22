# TrapDefense — AI Security Gateway (0.46)

> [モデル提供者への接続](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

[en](../en/aisg.md) · [ko](../ko/aisg.md) · [zh-CN](../zh-CN/aisg.md) · [ja](../ja/aisg.md) · [es](../es/aisg.md) · [fr](../fr/aisg.md)

対応するHTTP APIとリモートMCPサーバーを明示的なセキュリティ境界で接続します。エージェント単位の制御にはIDを追加します。

## 接続・識別・制御・検証

Dockerの合成環境を起動し、Access Brokerでエージェントを登録します。選択したツールへの自律アクセスを有効にし、認証情報を発行します。クライアントURLを変更しAuthorizationヘッダーで送信してください。許可・拒否の呼び出しと決定記録を確認します。

## ID方式の選択

ゲートウェイは接続キーまたは検証済みJWTを使用します。agent_keyは外部IAMなしで登録済みエージェントを識別します。JWT identity_mode: agentは検証済みテナントとエージェントのクレームを使用し、delegatedはユーザー・タスク・委任も要求します。既存エージェントは既定で委任が必要です。

## 認証情報の管理

有効期間は1時間、24時間、最大30日です。ハッシュのみ保存し、新しい認証情報は一度だけ表示します。ローテーションは旧キーを即時失効します。失効やエージェント無効化は以後の認証を拒否します。接続先の認証情報とは別です。

## 互換性と制限

インストールごとに固定接続先は一つです。明示的にマッピングされたHTTP JSONとステートレスMCP JSON POSTに対応します。SSE・状態セッション・stdio・WebSocket・SaaS内部呼び出しには非対応です。モデルAPIのbase_url変更だけでは個別のツール実行は経由しません。各URLと迂回防止のネットワーク設定が必要です。

## 承認

自律アクセスもツール・リソース・操作権限を確認します。高リスク操作には期限とリクエストに結び付いた承認が必要です。審査後、同じローカルキーの要求にX-TD-Approval-IDを追加して再試行すると承認を一度だけ消費します。Mirrorは承認を作成・消費しません。

## 検証範囲

ローカル合成検証は本番IdP・顧客経路・HA・容量の認証ではありません。Access Brokerは実験段階です。マネージドクラウドの登録は提供していません。

## クイックスタート

```bash
cd deploy/selfhost
docker compose -f compose.yaml -f compose.agent.yaml build app
docker compose -f compose.yaml -f compose.agent.yaml run --rm app init
docker compose -f compose.yaml -f compose.agent.yaml --profile smoke up -d
```

Console: `http://localhost:18080` · Gateway: `http://localhost:18084`

```text
API base_url: http://localhost:18084
MCP URL: http://localhost:18084/mcp
Authorization: Bearer <agent-credential>
```


```bash
# Set TD_AGENT_CREDENTIAL locally to the credential displayed once in the console.
# Register notes.read and enable autonomous access first.
curl --fail-with-body http://localhost:18084/api/notes \
  -H "Authorization: Bearer ${TD_AGENT_CREDENTIAL}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'

# Expected: HTTP 403. The fixture policy blocks notes.delete.
curl --fail-with-body http://localhost:18084/mcp \
  -H "Authorization: Bearer ${TD_AGENT_CREDENTIAL}" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"notes.delete","arguments":{}}}'
```

[Self-hosting](self-hosting.md) · [Identity](identity.md) · [Compatibility](gateway-compatibility.md)
