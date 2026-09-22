# TrapDefense — Open-source AI Security Gateway

[0.46: 有界の流入待機と検査器の容量]](docs/ja/latency.md) · [対話型ストリーミングの判断](docs/ja/interactive-streaming.md)

[0.44: Buffered SSE の遅延と導入適合性](docs/ja/latency.md)

## Least Privilege, Least Agency

**最小権限はアクセスを制限し、最小自律性は自律的な行動の範囲を定めます。**

設計原則は、エージェントに必要なアクセスだけを与え、独立して実行できる行動の範囲を定めることです。TrapDefense は既存の IAM と宛先サービスの権限を補完し、ゲートウェイ経由の対応する呼び出しに操作・データポリシーを適用します。任意のエージェント識別により、個別の権限範囲、委任、承認を制御できます。

[0.44: 運用ワークスペース（0.44）](docs/ja/operator-workspace.md)


[0.42: モデル → MCP → モデルの検証](docs/ja/agent-workflow.md)

**0.44:** [モデル提供者への接続](docs/ja/providers.md) — OpenAI · Anthropic · Gemini · OpenRouter.

**対応するHTTP APIとリモートMCPサーバーを明示的なセキュリティ境界で接続します。エージェント単位の制御にはIDを追加します。**

[接続・識別・制御・検証 →](docs/ja/aisg.md)

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Français](README.fr.md)

> **Open Source Preview 0.46:** ランタイムと運用 UI の全体を MIT で公開します。内蔵 Agent Access Broker は実装済みで合成検証も完了していますが、実 IdP、顧客ポリシー、HA、容量を検証するまでは **Experimental** です。

TrapDefense は、対応する HTTP / MCP トラフィック向けのセルフホスト型 AI Firewall です。リクエストとレスポンスを検査し、action・PII・secret ポリシーを適用し、サニタイズ済み証拠を保存します。必要に応じて、登録 agent、delegation、task、resource、action、1 回限りの human approval を使って認可します。

```text
AI agent → 認証 gateway → trusted request binding → Envoy + inspector
         → 任意の内蔵 Access Broker → Tool / MCP / HTTP API
```

## コンソール画面

合成データを使用した実際の 0.41 画面です。ダッシュボードには意図的な7秒のプロバイダー遅延テストが含まれ、性能ベンチマークではありません。Agent 管理は別のローカルデモです。

![ランタイムダッシュボード](docs/assets/console-dashboard-041.png)

<table>
<tr>
<td width="50%"><img src="docs/assets/console-agents-041.png" alt="Agent 権限 · 実験的機能"><br><strong>Agent 権限 · 実験的機能</strong></td>
<td width="50%"><img src="docs/assets/console-provider-041.png" alt="プロバイダー接続設定"><br><strong>プロバイダー接続設定</strong></td>
</tr>
</table>

## 1 つのオープンソース製品

Community / Enterprise のコード版は分けません。Runtime Gateway、HTTP/MCP 検査、PII/secret 防御、外部 OAuth JWT 検証、Agent Registry、delegation、Access Broker、human approval、audit、運用コンソール、Docker セルフホストをこの公開リポジトリに含めます。非公開ランタイムは不要です。

将来の有償サービスは managed cloud、fleet 運用、multi-node HA、外部 immutable audit、個別連携、サポートを対象にできます。現在のオープンソース強制機能をライセンスで隠す構成ではありません。[オープンソースモデル](docs/ja/editions.md)

## Docker セルフホスト

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
```

`http://localhost:18080` を開き、初期化時に設定した admin パスワードでログインします。クライアントは HTTP/MCP URL と `X-TD-Client-Key` または Bearer JWT を設定できる必要があります。対象サービスの credential は別管理です。[セルフホスト契約](docs/ja/self-hosting.md)

## 内蔵 Access Broker（Experimental）

Gateway-only モードは転送元とローカル検査ポリシーを検証し、agent identity を主張しません。Broker モードは外部 IdP が発行した JWT と明示的な claim mapping を要求します。検証済み claim のうち設定された値だけを正規化し、必須 identity が欠ける場合は転送前に拒否します。

Broker は tenant、registry、tool/resource scope、delegation、user、task、action、request digest、approval を確認します。高リスク action は `approval_required` となり、承認済みリクエストは一致する 1 回の実行にだけ使えます。対象サービスの権限や downstream OAuth token は TrapDefense の外側にあります。

## ローカルデモと検証

```bash
./scripts/install-console.sh
./scripts/run-console.sh
```

[http://127.0.0.1:5176](http://127.0.0.1:5176) で `admin` / `1234` を使い、Settings でパスワードを変更します。デモは実際のファイル型 Broker に合成 agent/delegation を登録し、「承認要求 → 承認 → 1 回実行 → 再利用拒否」を示します。

```bash
pip install -e ".[dev]"
pytest -q
npm run check --prefix console
npm run build --prefix console
```

これはソース・プロトコル・合成検証の証拠です。実 Entra/Okta/Keycloak tenant、Conditional Access、顧客 MCP 認証、強制ルーティング、HA、運用容量の証明ではありません。

[コンソール](docs/ja/console.md) · [アーキテクチャ](docs/ja/architecture.md) · [セキュリティ](docs/ja/security.md) · [移行](docs/ja/migration.md) · [英語基準文書](README.md)

## ライセンス

MIT。このリポジトリの Runtime Gateway と Access Broker はすべてオープンソースです。
