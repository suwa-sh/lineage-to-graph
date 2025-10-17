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

    subgraph TransactionDomain[TransactionDomain]
      TransactionDomain_id["id"]:::property
      TransactionDomain_userId["userId"]:::property
      TransactionDomain_createdAt["createdAt"]:::property
      TransactionDomain_money["money"]:::property
      TransactionDomain_metadata["metadata"]:::property
    end
    class TransactionDomain program_bg

    subgraph Money[Money]
      Money_amount["amount"]:::property
      Money_currency["currency"]:::property
    end
    class Money program_bg

    subgraph TransactionEntity[TransactionEntity]
      TransactionEntity_transactionId["transactionId"]:::property
      TransactionEntity_userId["userId"]:::property
      TransactionEntity_amount["amount"]:::property
      TransactionEntity_createdAt["createdAt"]:::property
    end
    class TransactionEntity program_bg

    subgraph HttpRequest[HttpRequest]
      HttpRequest_request_id["request_id"]:::property
      HttpRequest_user_id["user_id"]:::property
      HttpRequest_amount["amount"]:::property
      HttpRequest_timestamp["timestamp"]:::property
    end
    class HttpRequest program_bg

    subgraph Metadata[Metadata]
      Metadata_source["source"]:::property
      Metadata_version["version"]:::property
    end
    class Metadata program_bg

    subgraph transactions[transactions]
      transactions_transaction_id["transaction_id"]:::property
      transactions_user_id["user_id"]:::property
      transactions_amount["amount"]:::property
      transactions_created_at["created_at"]:::property
    end
    class transactions datastore_bg

  HttpRequest_request_id --> TransactionDomain_id
  HttpRequest_user_id --> TransactionDomain_userId
  HttpRequest_timestamp -->|"parse as timestamp"| TransactionDomain_createdAt
  HttpRequest_amount --> Money_amount
  lit_JPY["JPY"]:::literal
  lit_JPY --> Money_currency
  lit_api["api"]:::literal
  lit_api --> Metadata_source
  lit_v1_0["v1.0"]:::literal
  lit_v1_0 --> Metadata_version
  Money --> TransactionDomain_money
  Metadata --> TransactionDomain_metadata
  TransactionDomain_id --> TransactionEntity_transactionId
  TransactionDomain_userId --> TransactionEntity_userId
  TransactionDomain_money -->|"money.amount"| TransactionEntity_amount
  TransactionDomain_createdAt --> TransactionEntity_createdAt
  TransactionEntity_transactionId --> transactions_transaction_id
  TransactionEntity_userId --> transactions_user_id
  TransactionEntity_amount --> transactions_amount
  TransactionEntity_createdAt --> transactions_created_at
  TransactionDomain_id --> KafkaTransactionEvent_transaction_id
  lit_UUID["UUID生成"]:::literal
  lit_UUID --> KafkaTransactionEvent_event_id
  TransactionDomain_money -->|"money.amount"| KafkaTransactionEvent_amount
  KafkaTransactionEvent_transaction_id -->|"lookup from transactions"| transaction_history_transaction_id
  transactions_user_id -->|"join by transaction_id"| transaction_history_user_id
  transactions_amount -->|"join by transaction_id"| transaction_history_amount
  transaction_history_user_id --> user_balance_snapshot_user_id
  transaction_history_amount -->|"sum(history.amount) + kafka.amount"| user_balance_snapshot_total_amount
  KafkaTransactionEvent_amount --> user_balance_snapshot_total_amount
  lit_now["now()"]:::literal
  lit_now -->|"current timestamp"| user_balance_snapshot_last_updated

  style Money fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
  style Metadata fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
```

## 🚀 Features

| 機能 | 説明 |
|------|------|
| **📜 YAML定義 → Mermaid変換** | 各モデルとカラム、変換関係を記述したYAMLをMarkdownに変換。 |
| **⚡ シンプル構文** | `from`, `to`, `transform` の3要素だけで定義可能。 |
| **🏗️ 階層モデル対応** | モデルを入れ子にして階層構造を表現可能(例: Domain → ValueObject)。 |
| **📁 CSV対応** | モデル定義をCSVファイルから読み込み可能。大規模モデル管理に最適。 |
| **🔗 モデル参照** | モデル全体からフィールドへの参照をサポート(例: `Money → TransactionDomain.money`)。 |
| **🧱 JSON Schema 準拠** | `schema.json` によるバリデーション可能。 |


## 📂 Repository Structure

```
lineage-to-graph/
├── schema.json              # JSON Schema
├── requirements.txt         # Python依存関係
├── lineage_to_md.py        # YAML → Mermaid Markdown 変換スクリプト
└── data/
    ├── sample.yml          # 基本サンプル
    ├── event-driven.yml    # 全機能を網羅（階層構造、変換、多段階処理）
    ├── event-driven-csv.yml # CSV + モデル参照の実践例
    ├── etl-pipeline.yml    # 1カラム→複数カラムマッピング
    ├── レイアウト/          # CSVモデル定義（program）
    └── テーブル定義/        # CSVモデル定義（datastore）
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

## 📚 Samples

| サンプル | 説明 | カバーする機能 | ユースケース |
|---------|------|--------------|-------------|
| **sample.yml** | 最もシンプルな基本例 | フィールド間のマッピング、リテラル値 | REST API → RDB の基本フロー |
| **event-driven.yml** | 全機能を網羅した実践例 | 階層構造、複数ソース、変換、多段階処理 | Kafka + DDD（ValueObject）パターン |
| **event-driven-csv.yml** | CSV + モデル参照 | CSV読み込み、モデル→フィールド参照 | 大規模モデル管理 + ValueObject集約 |
| **etl-pipeline.yml** | 1カラム→複数カラム | 1:N マッピング、ETL多段階処理 | データレイク/DWH パイプライン |

### 個別生成

```bash
# 基本サンプル
python lineage_to_md.py data/sample.yml data/output/sample.md

# イベント駆動（階層構造）
python lineage_to_md.py data/event-driven.yml data/output/event-driven.md

# CSV + モデル参照
python lineage_to_md.py data/event-driven-csv.yml data/output/event-driven-csv.md \
  -p data/レイアウト -d data/テーブル定義

# ETLパイプライン
python lineage_to_md.py data/etl-pipeline.yml data/output/etl-pipeline.md
```

### 一括生成

すべてのサンプルを `data/output/` 配下に生成:

```bash
# YAML-onlyサンプル
for file in data/sample.yml data/event-driven.yml data/etl-pipeline.yml; do
  python lineage_to_md.py "$file" "data/output/$(basename "$file" .yml).md"
done

# CSVサンプル
python lineage_to_md.py data/event-driven-csv.yml data/output/event-driven-csv.md \
  -p data/レイアウト -d data/テーブル定義
```

---

## 📁 CSVからモデルを読み込む

大規模なデータモデルをCSVで管理し、リネージ定義はYAMLで記述できます。

### CSV形式

**ファイル名**: `論理名__物理名.csv`

```csv
論理名,物理名,データ型,サイズ,キー,説明
ユーザーID,user_id,VARCHAR,256,PK,
残高,total_amount,NUMBER,10,,
```

### 使用例

実践的なサンプル: [data/event-driven-csv.yml](data/event-driven-csv.yml)

```bash
python lineage_to_md.py \
  -p data/レイアウト \
  -d data/テーブル定義 \
  data/event-driven-csv.yml \
  data/output/event-driven-csv.md
```

このサンプルでは、以下のモデルがCSVから読み込まれます:

- `HttpRequest`, `TransactionDomain`, `Money`, `Metadata`, `TransactionEntity`

---

## 🧪 Schema Validation

YAMLの妥当性をチェックする場合:

```bash
pip install jsonschema
jsonschema -i data/sample.yml schema.json
```
