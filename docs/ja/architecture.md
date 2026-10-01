# アーキテクチャと信頼境界

**導入経路：**Docker 構成は[セルフホストガイド](self-hosting.md)に従います。別のソース版コンソールの Entra SSO・合成デモ設定は Docker に自動適用されません。

> **AISG:** [接続・識別・制御・検証](aisg.md). ゲートウェイは接続キーまたは検証済みJWTを使用します。agent_keyは外部IAMなしで登録済みエージェントを識別します。JWT identity_mode: agentは検証済みテナントとエージェントのクレームを使用し、delegatedはユーザー・タスク・委任も要求します。既存エージェントは既定で委任が必要です。

[English](../en/architecture.md) · [한국어](../ko/architecture.md) · [简体中文](../zh-CN/architecture.md) · [日本語](../ja/architecture.md) · [Español](../es/architecture.md) · [Français](../fr/architecture.md)

> **0.47:** コンソール（コントロールプレーン）とゲートウェイ・検査器（データプレーン）は別プロセスです。ポリシーは Ed25519 署名済みスナップショットとしてのみデータプレーンに届き、証跡は追記専用の spool で戻ります。[プレーン分離](plane-separation.md)を参照してください。

コンソールは単一テナント Microsoft Entra ID SSO と管理者・閲覧者ロールをサポートします。コンソール運用者の認証とエージェント認可は別の境界で、認可は内蔵 Access Broker が行います。 [Entra SSO](identity.md).

```text
AI agents → TrapDefense AI Firewall → Tools / MCP servers / APIs
            Action policy · Data protection · Audit
          ← Inspected responses ←
```

## データ経路と管理経路

管理 API はローカル運用者を認証し、ポリシーを保存して UI を提供します。Envoy は対応 HTTP/MCP 通信を転送し、gRPC ExtProc で要求・応答を検査します。各ストリームは開始時のポリシーを保持します。副作用のない合成 HTTP 宛先が受信証跡を提供します。[導入手順](console.md)を参照してください。

## 信頼契約

1. TrapDefense 外部で経路を強制し、保護通信の迂回を防ぎます。
2. クライアント HTTPS は TLS ingress で終端し、同梱の署名アダプターを使います。外部 TLS 復号装置は別途設計するネットワーク連携の選択肢で、base_url/MCP URL 構成の必須条件ではありません。
3. 信頼済みアダプターがクライアント由来の `x-td-*`、`x-asr-*` を除去し、実際に観察した要求へ署名します。method・authority・path/query・アプリケーションヘッダー・完全な本文を保持します。結合規則と除外項目は `inspection/identity.py` にあります。
4. HMAC キーは信頼済みホップと検査器だけに保管し、エージェントへ渡しません。gateway-only の `source_id` を許可リスト化し、平文と ExtProc の経路を隔離します。例は公開 gRPC 待受を認証しません。
5. Envoy は本文全体のバッファリング、サイズ・時間上限、`failure_mode_allow: false` を使い、転送前に証明ヘッダーを除去します。署名は元要求に、永続的承認がある場合はマスキング後の操作ダイジェストに結び付きます。
6. Gateway-only モードは明示的な経路・ツール・リソース・操作のローカルルールと転送元を検証し、ユーザー認証や委任権限を保証しません。
7. Broker モードは検証済み JWT identity claim と内蔵 registry、delegation、task、resource、action、1 回限りの approval を評価します。必須 identity がなければ fail closed します。

任意の TLS 装置へ自動適用できる万能アダプターはありません。メタデータ偽装と上流への直接アクセスを防ぐ統合が必要です。

## 対応範囲と制限

経路は authority・method・path・必要ヘッダーに厳密一致します。MCP は明示的に対応付けた JSON-RPC 呼び出しと設定バージョンが対象で、全機能の認証ではありません。任意の MCP トランスポート、WebSocket トンネル、暗号化本文、無制限 CONNECT、自動通信検出は対象外です。マスキングは許可フィールド・形式に限定し、危険な変換は遮断します。シグネチャは既知パターンの限定的検出であり、全プロンプト攻撃を防ぐ保証ではありません。SSE は制限内の完全なストリームをバッファリングし、無制限の逐次トークン処理ではありません。

独立した mirror 収集器はコピーを受信し、原本を遮断・変更できません。ヘッダーのみなら範囲は不完全です。コンソールの Mirror は同期経路を本文変更なしで観察しますが、検査通信障害は遮断します。両者を配置・報告で区別してください。JSONL 証跡と SQLite 監査は原文・キーを含みませんが、編集可能なローカル保存で、不変保持サービスではありません。

## ネットワーク

ループバックと digest 固定の amd64/arm64 Envoy を使用します。macOS は Docker Desktop のホスト転送、Linux は host networking です。NIC 一覧は物理ポート数ではなく OS のインターフェースです。2 NIC ルーティング、透過ブリッジ、送信 NIC 固定、実 IdP/TLS、HA、本番性能は別途作業です。agentgateway の任意テストは互換性確認であり、管理型ゲートウェイではありません。
