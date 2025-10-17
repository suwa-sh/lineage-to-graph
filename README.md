# 🧩 lineage-to-graph

**Column-level Data Lineage → Markdown/Mermaid Graph Converter**

`lineage-to-graph` は、  
YAML または JSON 形式で定義した **カラム単位のデータリネージ情報** を  
自動的に **Markdown + Mermaid** 図へ変換するツールです。  
システム設計書・ETLドキュメント・アーキテクチャレビューなどで、  
軽量かつ一貫したリネージ表現を実現します。

```mermaid
graph LR
  classDef program_bg fill:#E3F2FD,stroke:#1565C0,stroke-width:2px;
  classDef datastore_bg fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px;
  classDef property fill:#F5F5F5,stroke:#9E9E9E,stroke-width:1px,color:#424242;
  classDef literal fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px,color:#BF360C;

    subgraph HttpRequest[HttpRequest]
      HttpRequest_request_id["request_id"]:::property
      HttpRequest_user_id["user_id"]:::property
      HttpRequest_amount["amount"]:::property
      HttpRequest_timestamp["timestamp"]:::property
    end
    class HttpRequest program_bg

    subgraph TransactionDomain[TransactionDomain]
      TransactionDomain_id["id"]:::property
      TransactionDomain_userId["userId"]:::property
      TransactionDomain_createdAt["createdAt"]:::property

      subgraph TransactionDomain_MoneyValueObject[MoneyValueObject]
        TransactionDomain_MoneyValueObject_amount["amount"]:::property
        TransactionDomain_MoneyValueObject_currency["currency"]:::property
      end
      class TransactionDomain_MoneyValueObject program_bg
      subgraph TransactionDomain_MetadataValueObject[MetadataValueObject]
        TransactionDomain_MetadataValueObject_source["source"]:::property
        TransactionDomain_MetadataValueObject_version["version"]:::property
      end
      class TransactionDomain_MetadataValueObject program_bg
    end
    class TransactionDomain program_bg

    subgraph TransactionEntity[TransactionEntity]
      TransactionEntity_transactionId["transactionId"]:::property
      TransactionEntity_userId["userId"]:::property
      TransactionEntity_amount["amount"]:::property
      TransactionEntity_createdAt["createdAt"]:::property
    end
    class TransactionEntity program_bg

    subgraph transactions[transactions]
      transactions_transaction_id["transaction_id"]:::property
      transactions_user_id["user_id"]:::property
      transactions_amount["amount"]:::property
      transactions_created_at["created_at"]:::property
    end
    class transactions datastore_bg

    subgraph KafkaTransactionEvent[KafkaTransactionEvent]
      KafkaTransactionEvent_event_id["event_id"]:::property
      KafkaTransactionEvent_transaction_id["transaction_id"]:::property
      KafkaTransactionEvent_amount["amount"]:::property
    end
    class KafkaTransactionEvent program_bg

    subgraph transaction_history[transaction_history]
      transaction_history_user_id["user_id"]:::property
      transaction_history_transaction_id["transaction_id"]:::property
      transaction_history_amount["amount"]:::property
    end
    class transaction_history datastore_bg

    subgraph user_balance_snapshot[user_balance_snapshot]
      user_balance_snapshot_user_id["user_id"]:::property
      user_balance_snapshot_total_amount["total_amount"]:::property
      user_balance_snapshot_last_updated["last_updated"]:::property
    end
    class user_balance_snapshot datastore_bg

  HttpRequest_request_id --> TransactionDomain_id
  HttpRequest_user_id --> TransactionDomain_userId
  HttpRequest_amount --> TransactionDomain_MoneyValueObject_amount
  lit_JPY["JPY"]:::literal
  lit_JPY --> TransactionDomain_MoneyValueObject_currency
  HttpRequest_timestamp -->|"parse as timestamp"| TransactionDomain_createdAt
  lit_api["api"]:::literal
  lit_api --> TransactionDomain_MetadataValueObject_source
  lit_v1_0["v1.0"]:::literal
  lit_v1_0 --> TransactionDomain_MetadataValueObject_version
  TransactionDomain_id --> TransactionEntity_transactionId
  TransactionDomain_userId --> TransactionEntity_userId
  TransactionDomain_MoneyValueObject_amount --> TransactionEntity_amount
  TransactionDomain_createdAt --> TransactionEntity_createdAt
  TransactionEntity_transactionId --> transactions_transaction_id
  TransactionEntity_userId --> transactions_user_id
  TransactionEntity_amount --> transactions_amount
  TransactionEntity_createdAt --> transactions_created_at
  TransactionDomain_id --> KafkaTransactionEvent_transaction_id
  TransactionDomain_id -->|"generate UUID from transaction_id"| KafkaTransactionEvent_event_id
  TransactionDomain_MoneyValueObject_amount --> KafkaTransactionEvent_amount
  KafkaTransactionEvent_transaction_id -->|"lookup from transactions"| transaction_history_transaction_id
  transactions_user_id -->|"join by transaction_id"| transaction_history_user_id
  transactions_amount -->|"join by transaction_id"| transaction_history_amount
  transaction_history_user_id --> user_balance_snapshot_user_id
  transaction_history_amount -->|"sum(history.amount) + kafka.amount"| user_balance_snapshot_total_amount
  KafkaTransactionEvent_amount --> user_balance_snapshot_total_amount
  lit_now["now()"]:::literal
  lit_now -->|"current timestamp"| user_balance_snapshot_last_updated
```


## 🚀 Features

| 機能 | 説明 |
|------|------|
| **📜 YAML定義 → Mermaid変換** | 各モデルとカラム、変換関係を記述したYAMLをMarkdownに変換。 |
| **⚡ シンプル構文** | `from`, `to`, `transform` の3要素だけで定義可能。 |
| **🏗️ 階層モデル対応** | モデルを入れ子にして階層構造を表現可能(例: Domain → ValueObject)。 |
| **🧱 JSON Schema 準拠** | `schema.json` によるバリデーション可能。 |


## 📂 Repository Structure

```
lineage-to-graph/
├── schema.json              # JSON Schema
├── requirements.txt         # Python依存関係
├── data/
│   ├── sample.yml          # 基本サンプル（ETL + 集計）
│   ├── simple.yml          # シンプルな1対1マッピング
│   ├── multi-source.yml    # 複数ソース統合
│   ├── transformation-heavy.yml  # データ変換重視
│   ├── etl-pipeline.yml    # 多段階ETLパイプライン
│   └── event-driven.yml    # イベント駆動アーキテクチャ
└── lineage_to_md.py        # YAML → Mermaid Markdown 変換スクリプト
```


## 🧱 Schema Specification

[schema.json](./schema.json)


## 🧰 Usage

### 1. 依存関係のインストール

Python 3.8+ が必要です。

```bash
pip install -r requirements.txt
```

### 2. 実行
```bash
python lineage_to_md.py data/sample.yml data/output/output.md
```

## 📚 Sample Files & Use Cases

### 1. **simple.yml** - 基本的な1対1マッピング

最もシンプルなフィールド変換。初心者向け。

```bash
python lineage_to_md.py data/simple.yml data/output/simple.md
```

**ユースケース**: REST APIレスポンス → データベーステーブル

### 2. **multi-source.yml** - 複数ソースからの統合

複数のデータソースから1つのターゲットへ統合。

```bash
python lineage_to_md.py data/multi-source.yml data/output/multi-source.md
```

**ユースケース**: CRM、請求、マーケティングデータの顧客マスタ統合

### 3. **transformation-heavy.yml** - データ変換処理のショーケース

型変換、通貨変換、ルックアップなど様々な変換例。

```bash
python lineage_to_md.py data/transformation-heavy.yml data/output/transformation-heavy.md
```

**ユースケース**: 生データのクレンジングと正規化

### 4. **etl-pipeline.yml** - 多段階ETLパイプライン

Raw → Staging → DWH → Mart の4層アーキテクチャ。

```bash
python lineage_to_md.py data/etl-pipeline.yml data/output/etl-pipeline.md
```

**ユースケース**: データレイク/データウェアハウスの実践的なパイプライン

### 5. **event-driven.yml** - イベント駆動アーキテクチャ + 階層モデル

HTTPリクエスト → Domain(ValueObject含む) → RDB → Kafka → サブスクライブ → 集計更新。

```bash
python lineage_to_md.py data/event-driven.yml data/output/event-driven.md
```

**ユースケース**: Kafkaを使ったCQRS/イベントソーシングパターン、DDDのValueObject表現


## 🧪 Schema Validation

YAMLの妥当性をチェックする場合:

```bash
pip install jsonschema
jsonschema -i data/sample.yml schema.json
```
