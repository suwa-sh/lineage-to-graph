# 🧩 lineage-to-graph

**Column-level Data Lineage Visualization Tools**

- lineage.yml

  ```yml
  spec: lineage-v1

  models:
    - name: UserDto
      type: program
      props: [name, country]

    - name: user_table
      type: datastore
      props: [name, country, load_timestamp]

  lineage:
    - { from: UserDto.name,    to: user_table.name }
    - { from: UserDto.country, to: user_table.country, transform: toUpperCase }
    - { from: JP,              to: user_table.country, transform: デフォルト値 }
    - { from: now(),           to: user_table.load_timestamp, transform: as load_timestamp }
  ```

- output image

  ```mermaid
  graph LR
    classDef program_bg fill:#E3F2FD,stroke:#1565C0,stroke-width:2px;
    classDef datastore_bg fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px;
    classDef property fill:#F5F5F5,stroke:#9E9E9E,stroke-width:1px,color:#424242;
    classDef literal fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px,color:#BF360C;

      subgraph UserDto[UserDto]
        UserDto_name["name"]:::property
        UserDto_country["country"]:::property
      end
      class UserDto program_bg

      subgraph user_table[user_table]
        user_table_name["name"]:::property
        user_table_country["country"]:::property
        user_table_load_timestamp["load_timestamp"]:::property
      end
      class user_table datastore_bg

    UserDto_name --> user_table_name
    UserDto_country -->|"toUpperCase"| user_table_country
    lit_JP["JP"]:::literal
    lit_JP -->|"デフォルト値"| user_table_country
    lit_now["now()"]:::literal
    lit_now -->|"as load_timestamp"| user_table_load_timestamp
  ```

## Schema定義

[schema.json](./schema.json)

## リポジトリ構成

```txt
lineage-to-graph/
├── schema.json              # JSON Schema
├── requirements.txt         # Python依存関係
├── lineage_to_md.py         # YAML → Mermaid Markdown 変換スクリプト
└── data/                    # サンプルデータ
```

## schema_validation

```bash
pip install jsonschema
jsonschema -i data/sample.yml schema.json
```

## lineage_to_md

YAML形式で定義した **カラム単位のデータリネージ情報** を **Markdown + Mermaid** 図へ変換するツールです。  
システム設計書・ETLドキュメント・アーキテクチャレビューなどで、軽量かつ一貫したリネージ表現を実現します。

![](https://share.cleanshot.com/17MNBzGC+)

### 機能

| 機能                           | 説明                                                                                                  |
| ------------------------------ | ----------------------------------------------------------------------------------------------------- |
| **📜 YAML定義 → Mermaid変換**   | 各モデルとカラム、変換関係を記述したYAMLをMarkdownに変換。                                           |
| **⚡ シンプル構文**             | `from`, `to`, `transform` の3要素だけで定義可能。                                                     |
| **🏗️ 階層モデル対応**           | モデルを入れ子にして階層構造を表現可能(例: Domain → ValueObject)。                                   |
| **📁 CSV対応**                  | モデル定義をCSVファイルから読み込み可能。大規模モデル管理に最適。                                    |
| **🌐 OpenAPI対応**              | OpenAPI 3.x仕様からスキーマ定義を読み込み可能。API設計書との同期が容易。                              |
| **📡 AsyncAPI対応**             | AsyncAPI 3.x仕様からスキーマ定義を読み込み可能。`$ref` による参照もサポート。イベント駆動設計に最適。 |
| **🎯 フィールドフィルタリング** | CSV読み込み時、使用フィールドのみ表示。大規模CSV(50+フィールド)でも図がシンプル。                    |
| **🔗 モデル参照**               | モデル全体からフィールドへの参照をサポート(例: `Money → TransactionDomain.money`)。                  |
| **🔢 モデルインスタンス**       | 同じ型の複数インスタンスを表現可能(例: `Money#jpy`, `Money#usd`)。1つのCSVで複数インスタンスに対応。 |
| **✨ props省略可能**             | YAML定義でmodel.propsを省略し、lineageから自動生成。プロトタイピングや段階的詳細化に最適。                 |
| **🧱 JSON Schema 準拠**         | `schema.json` によるバリデーション可能。                                                             |

### 利用方法

#### 1. 依存関係のインストール

Python 3.8+ が必要です。

```bash
pip install -r requirements.txt
```

#### 2. 基本的な実行

```bash
# YAMLのみ使用
python lineage_to_md.py data/sample.yml data/output/output.md

# CSVモデル読み込み (使用フィールドのみ表示 - デフォルト)
python lineage_to_md.py data/event-driven-csv.yml data/output/output.md \
  --program-model-dir data/レイアウト \
  --datastore-model-dir data/テーブル定義

# OpenAPIモデル読み込み
python lineage_to_md.py data/api_example.yml data/output/output.md \
  --openapi-spec data/openapi/user-api.yaml

# AsyncAPIモデル読み込み
python lineage_to_md.py data/api_example.yml data/output/output.md \
  --asyncapi-spec data/asyncapi/user-events.yaml

# 複数ソース統合 (CSV + OpenAPI + AsyncAPI)
python lineage_to_md.py data/api_example.yml data/output/output.md \
  --program-model-dir data/レイアウト \
  --openapi-spec data/openapi/user-api.yaml \
  --asyncapi-spec data/asyncapi/user-events.yaml

# CSVモデル読み込み (全フィールド表示)
python lineage_to_md.py data/event-driven-csv.yml data/output/output.md \
  --program-model-dir data/レイアウト \
  --datastore-model-dir data/テーブル定義 \
  --show-all-props
```

#### 3. コマンドラインオプション

| オプション              | 短縮形 | 説明                                                              |
| ----------------------- | ------ | ----------------------------------------------------------------- |
| `--program-model-dir`   | `-p`   | programタイプのCSVモデルが格納されたディレクトリ(複数指定可)      |
| `--datastore-model-dir` | `-d`   | datastoreタイプのCSVモデルが格納されたディレクトリ(複数指定可)    |
| `--openapi-spec`        | `-o`   | OpenAPI仕様ファイル (YAML/JSON形式) (複数指定可)                  |
| `--asyncapi-spec`       | `-a`   | AsyncAPI仕様ファイル (YAML/JSON形式) (複数指定可)                 |
| `--show-all-props`      | なし   | CSV読み込み時に全プロパティを表示(デフォルトは使用フィールドのみ) |

**使用例:**
```bash
# 短縮形を使用
python lineage_to_md.py data/lineage.yml output.md -p data/models -d data/tables

# 複数ディレクトリ指定
python lineage_to_md.py data/lineage.yml output.md \
  -p data/models1 -p data/models2 \
  -d data/tables1 -d data/tables2
```

### サンプル

| サンプル                     | 説明                      | カバーする機能                         | ユースケース                  |
| ---------------------------- | ------------------------- | -------------------------------------- | ----------------------------- |
| **sample.yml**               | 最もシンプルな基本例      | フィールド間のマッピング、リテラル値   | REST API → RDB の基本フロー   |
| **event-driven.yml**         | 多くの機能を網羅          | 階層構造、複数ソース、変換、多段階処理 | DDD + Kafka                   |
| **event-driven-csv.yml**     | CSV + モデル参照          | CSV読み込み、モデル→フィールド参照     | DDD + Kafka                   |
| **instance_example.yml**     | モデルインスタンス (YAML) | 同じ型の複数インスタンス、モデル参照   | 複数通貨の金額管理            |
| **instance_csv_example.yml** | モデルインスタンス (CSV)      | CSV読み込み + インスタンス             | 複数通貨の金額管理 (CSV使用)  |
| **api_example.yml**          | OpenAPI + AsyncAPI            | API仕様からモデル読み込み              | API → イベント → DB           |
| **test-dynamic-fields.yml**  | props省略 + 動的生成           | 動的フィールド生成、階層構造自動作成   | プロトタイピング、軽量定義    |
| **etl-pipeline.yml**         | 1カラム→複数カラム            | 1:N マッピング、ETL多段階処理          | データレイク/DWH パイプライン |

#### 個別生成

```bash
# 基本サンプル
python lineage_to_md.py data/sample.yml data/output/sample.md

# イベント駆動（階層構造）
python lineage_to_md.py data/event-driven.yml data/output/event-driven.md

# CSV + モデル参照 (使用フィールドのみ)
python lineage_to_md.py data/event-driven-csv.yml data/output/event-driven-csv.md \
  -p data/レイアウト -d data/テーブル定義

# モデルインスタンス（YAML定義）
python lineage_to_md.py data/instance_example.yml data/output/instance_example.md

# モデルインスタンス（CSV読み込み）
python lineage_to_md.py data/instance_csv_example.yml data/output/instance_csv_example.md \
  -p data/レイアウト

# OpenAPI + AsyncAPI
python lineage_to_md.py data/api_example.yml data/output/api_example.md \
  -o data/openapi/user-api.yaml \
  -a data/asyncapi/user-events.yaml

# props省略 + 動的生成
python lineage_to_md.py data/dynamic-fields.yml data/output/dynamic-fields.md

# ETLパイプライン
python lineage_to_md.py data/etl-pipeline.yml data/output/etl-pipeline.md
```

#### 4. Claude Code Agent Skills

[Claude Code](https://claude.com/claude-code) を使って、lineage定義の作成・実装コード生成・逆引きを支援するエージェントスキルを提供しています。

##### インストール

```bash
git clone https://github.com/suwa-sh/lineage-to-graph.git
cd lineage-to-graph

# グローバルにインストール（全プロジェクトで利用可能）
bash scripts/install-skills.sh --global

# プロジェクトローカルにインストール
bash scripts/install-skills.sh --local /path/to/my-project
```

##### スキル一覧

| スキル | トリガー例 | 説明 |
| --- | --- | --- |
| **lineage-create** | 「lineage定義を作成」 | データモデル定義やエントリーポイントからlineage YAMLを生成 |
| **lineage-to-code** | 「lineageから実装」 | lineage定義を読み取り、プロジェクトに合わせたマッピングコードを生成 |
| **code-to-lineage** | 「コードからlineage」 | 実装コードのコールスタックを追跡してlineage定義を逆引き生成 |

※ `lineage-core` は共有リソース（スキーマ仕様、YAMLパターン集、変換スクリプト）を提供する内部スキルです。
※ 依存パッケージのインストールは `install-skills.sh` 実行時に自動で行われます。

##### スキル構成

```txt
.claude/skills/
├── lineage-core/          # 共有リソース（変換スクリプト、リファレンス）
│   ├── scripts/           #   lineage_to_md.py, requirements.txt
│   └── references/        #   schema-spec.md, yaml-patterns.md, lineage-reading-guide.md
├── lineage-create/        # lineage定義の新規作成
├── lineage-to-code/       # lineage → 実装コード生成
└── code-to-lineage/       # 実装 → lineage定義の逆引き
```

### 詳細機能

#### リテラル値の扱い

リテラル値（モデルやフィールドではない固定値）は、lineage定義ごとに一意のノードとして生成されます。

**動作例:**

```yaml
lineage:
  - { from: JP, to: user_table.country }
  - { from: JP, to: transaction.country }
```

**生成されるMermaid:**

```mermaid
lit_1["JP"]:::literal
lit_1 --> user_table_country

lit_2["JP"]:::literal
lit_2 --> transaction_country
```

→ 同じラベル `"JP"` でも、異なるlineageエントリでは別々のノードとして生成されます。これにより、各リネージの独立性が保たれ、複雑な図でも追跡が容易になります。

#### AsyncAPI 3.0 の $ref サポート

AsyncAPI 3.0 仕様では、`components/schemas` セクションでスキーマを定義し、`$ref` で参照できます。

**AsyncAPI 3.0 サンプル:**

```yaml
asyncapi: 3.0.0
components:
  schemas:
    UserBase:
      type: object
      properties:
        userId: {type: string}
        name: {type: string}

    UserCreated:
      allOf:
        - $ref: "#/components/schemas/UserBase"
        - type: object
          properties:
            registrationSource: {type: string}
```

→ `UserCreated` は `UserBase` のプロパティ (`userId`, `name`) と自身のプロパティ (`registrationSource`) を持つモデルとして読み込まれます。

**lineageでの利用:**

```yaml
lineage:
  - from: HttpRequest.user_id
    to: UserCreated.userId
  - from: HttpRequest.name
    to: UserCreated.name
```
