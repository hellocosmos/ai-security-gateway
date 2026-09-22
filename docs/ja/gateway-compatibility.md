# ゲートウェイクライアント互換性 — 0.45

> [モデル提供者への接続](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [接続・識別・制御・検証](aisg.md). ゲートウェイは接続キーまたは検証済みJWTを使用します。agent_keyは外部IAMなしで登録済みエージェントを識別します。JWT identity_mode: agentは検証済みテナントとエージェントのクレームを使用し、delegatedはユーザー・タスク・委任も要求します。既存エージェントは既定で委任が必要です。

[English](../en/gateway-compatibility.md) · [한국어](../ko/gateway-compatibility.md) · [简体中文](../zh-CN/gateway-compatibility.md) · [日本語](../ja/gateway-compatibility.md) · [Español](../es/gateway-compatibility.md) · [Français](../fr/gateway-compatibility.md)

クライアントはリモート HTTP/MCP URL を TrapDefense に変更し、接続キーのヘッダーまたは OAuth Bearer JWT を送信できる必要があります。クライアント→TrapDefense と TrapDefense→宛先の認証は分離されます。

| 経路 | 0.42 の証拠 |
|---|---|
| 一般 JSON HTTP | HTTPX による合成統合を検証済み |
| 公式 Python MCP SDK 1.30.0 | MCP `2025-11-25` の初期化、通知、ツール一覧を合成統合で検証済み |
| Entra 形式 OAuth | `scp`、`tid`、`oid`、`azp` と discovery、DCR、PKCE、resource binding を合成検証。実 Entra tenant は未検証 |
| Okta 形式 OAuth | 配列 `scp` と `cid` を完全な合成フローで検証。実 Okta server は未検証 |
| Keycloak 形式 / 実ローカル | 合成フローに加え、digest 固定の公式 Keycloak 26.7.3 が発行した実ローカルトークンと discovery/JWKS を検証済み |
| VS Code 1.135 リモート MCP | 実インストール製品で `Running`、1 ツール検出、3 件の MCP receipt、`2025-11-25` 初期化要求を確認 |
| Stateful MCP、長時間 SSE、WebSocket、stdio | 未対応。session header と upstream SSE は fail closed |
| マルチノード HA | 未対応。ローカル SQLite、replay、audit state を持つ単一 gateway 構成 |

`gateway_auth` は `client_key` または `jwt` を使用します。JWT モードの TrapDefense は OAuth Resource Server で、RFC 9728 metadata と `WWW-Authenticate` を提供します。`scope`/`scp` は空白区切り文字列または文字列配列を受け付け、任意の `authorized_parties` は `azp`、`appid`、`cid` を制限します。0.42 は Entra の `roles` app role を scope として扱いません。

`target_auth` は `none`、`passthrough_bearer`、`static_bearer`、`static_api_key` をサポートします。Gateway JWT は宛先に転送されません。ログイン、token 発行、refresh、OBO は外部 IdP または別の credential provider が担当します。

実統合を承認する前に、URL 変更、両側の認証、MCP 初期化/検出、許可・拒否、宛先副作用、PII/secret、宛先 401、検査障害、直接 URL fallback を確認してください。再現手順、設定、出典は[英語ガイド](../en/gateway-compatibility.md)を参照してください。


現在の証拠には実 OpenAI→合成 MCP、公式プロバイダー SDK の合成試験、実ローカル MCP/Keycloak、VS Code 初期化・検索が含まれます。モデル SSE は全体バッファ方式です。ステートフル MCP、顧客 IAM、ホスト間 HA、本番容量の認証ではありません。[0.42 検証と限界](agent-workflow.md)を参照してください。
