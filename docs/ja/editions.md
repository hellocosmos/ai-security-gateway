# 1 つのオープンソース製品

> **AISG:** [接続・識別・制御・検証](aisg.md). ゲートウェイは接続キーまたは検証済みJWTを使用します。agent_keyは外部IAMなしで登録済みエージェントを識別します。JWT identity_mode: agentは検証済みテナントとエージェントのクレームを使用し、delegatedはユーザー・タスク・委任も要求します。既存エージェントは既定で委任が必要です。

[English](../en/editions.md) · [한국어](../ko/editions.md) · [简体中文](../zh-CN/editions.md) · [日本語](../ja/editions.md) · [Español](../es/editions.md) · [Français](../fr/editions.md)

TrapDefense 0.44 は単一の MIT ライセンスコードベースです。Runtime Gateway と Agent Access Broker を同じ公開リポジトリで提供し、非公開 Python 配布物、provider entry point、license key、edition switch は不要です。

## 提供状況

| 境界 | 状態 | 証拠と制限 |
|---|---|---|
| Runtime Gateway とコンソール | **Open Source Preview** | 公開ソース、CI、合成 Envoy 経路、HTTP/MCP ポリシー、PII/secret 制御、ローカル UI。実環境のルーティングと容量は個別検証が必要です。 |
| 内蔵 Agent Access Broker | **Experimental** | registry、delegation、厳密な認可、tenant 分離、ファイルトランザクション、リクエストに結び付く一回限りの承認を公開。実顧客 IdP/ポリシーと multi-node 検証は未完了です。 |
| Docker セルフホスト | **Preview** | adapter、Envoy、inspector、console、gateway 認証、独立した target credential をソースから構築。1 インストールにつき固定 destination 1 つです。 |
| Managed cloud、fleet、multi-node HA、外部 immutable audit | **Planned** | 現在は提供していません。 |

Gateway-only はローカル検査ポリシーと trusted source を検証します。Broker-enabled は検証済み JWT identity mapping、agent registry、delegation、resource/action 認可、approval を追加します。両方とも同じオープンソースパッケージです。

将来の有償サービスは、同じランタイムを運用する managed service、fleet lifecycle、multi-node HA、外部 audit、顧客 connector、ポリシー導入、SLA、サポートです。これはサービス運用の境界であり、ソース機能の制限ではありません。

ファイル store は同一ホストの POSIX プロセス向けで、分散 DB ではありません。NFS/SMB を使った multi-host HA には利用できません。合成テストは実 IdP、Conditional Access、顧客 MCP 認証、TLS ルーティング、容量の認証ではありません。

[Docker 0.44](self-hosting.md) · [アーキテクチャ](architecture.md) · [セキュリティ](security.md) · [互換性](gateway-compatibility.md)
