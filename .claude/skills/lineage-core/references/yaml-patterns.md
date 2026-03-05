# lineage YAML パターン集

## パターン1: 基本的なフィールドマッピング

DTO からテーブルへの単純なマッピング。

```yaml
spec: lineage-v1

models:
  - name: UserDto
    type: program
    props: [name, country]

  - name: user_table
    type: datastore
    props: [name, country, load_timestamp]

lineage:
  - { from: UserDto.name, to: user_table.name }
  - { from: UserDto.country, to: user_table.country, transform: toUpperCase }
  - { from: JP, to: user_table.country, transform: デフォルト値 }
  - { from: now(), to: user_table.load_timestamp }
```

## パターン2: 階層構造（ValueObject）

Domain + ValueObject の入れ子構造。

```yaml
spec: lineage-v1

models:
  - name: HttpRequest
    type: program
    props: [request_id, user_id, amount, timestamp]

  - name: TransactionDomain
    type: program
    props: [id, userId, createdAt]
    children:
      - name: MoneyValueObject
        type: program
        props: [amount, currency]

lineage:
  - { from: HttpRequest.request_id, to: TransactionDomain.id }
  - { from: HttpRequest.user_id, to: TransactionDomain.userId }
  - { from: HttpRequest.amount, to: TransactionDomain.MoneyValueObject.amount }
  - { from: JP, to: TransactionDomain.MoneyValueObject.currency }
  - { from: HttpRequest.timestamp, to: TransactionDomain.createdAt }
```

## パターン3: モデルインスタンス

同じモデルを異なるコンテキストで使用。

```yaml
spec: lineage-v1

models:
  - name: HttpRequest
    type: program
    props: [amount_jpy, amount_usd]

  - name: Money
    type: program
    props: [amount, currency]

  - name: Transaction
    type: datastore
    props: [amount_jpy, amount_usd]

lineage:
  - { from: HttpRequest.amount_jpy, to: Money#jpy.amount }
  - { from: JP, to: Money#jpy.currency }
  - { from: HttpRequest.amount_usd, to: Money#usd.amount }
  - { from: US, to: Money#usd.currency }
  - { from: Money#jpy, to: Transaction.amount_jpy, transform: "save JPY" }
  - { from: Money#usd, to: Transaction.amount_usd, transform: "save USD" }
```

## パターン4: 多段階ETLパイプライン

Raw → Staging → DWH → Mart の4層アーキテクチャ。

```yaml
spec: lineage-v1

models:
  - name: raw_sales_log
    type: datastore
    props: [log_id, timestamp, product_code, quantity, price]

  - name: stg_sales
    type: datastore
    props: [sale_id, sale_date, product_id, qty, unit_price, total_price]

  - name: dwh_sales_fact
    type: datastore
    props: [fact_id, date_key, product_key, quantity, revenue]

lineage:
  # Raw → Staging
  - { from: raw_sales_log.log_id, to: stg_sales.sale_id }
  - { from: raw_sales_log.timestamp, to: stg_sales.sale_date, transform: "cast to date" }
  - { from: raw_sales_log.product_code, to: stg_sales.product_id, transform: "lookup master" }
  - { from: [raw_sales_log.quantity, raw_sales_log.price], to: stg_sales.total_price, transform: "quantity * price" }

  # Staging → DWH
  - { from: stg_sales.sale_date, to: dwh_sales_fact.date_key, transform: "join dim_date" }
  - { from: stg_sales.total_price, to: dwh_sales_fact.revenue }
```

## パターン5: CSV外部モデル

models を空にし、CSV からモデルを読み込む。

```yaml
spec: lineage-v1

models: []

lineage:
  - { from: HttpRequest.amount, to: TransactionEntity.amount }
  - { from: TransactionEntity.amount, to: transactions.amount }
```

実行コマンド:
```bash
python3 lineage_to_md.py lineage.yml output.md \
  --program-model-dir data/レイアウト \
  --datastore-model-dir data/テーブル定義
```

## パターン6: props省略（動的生成）

props を省略し、lineage 参照から自動生成。

```yaml
spec: lineage-v1

models:
  - name: InputModel
    type: program
  - name: OutputModel
    type: datastore

lineage:
  - { from: InputModel.field1, to: OutputModel.field1 }
  - { from: InputModel.field2, to: OutputModel.field2, transform: "convert" }
  - { from: default_value, to: OutputModel.field3 }
```

## パターン7: モデル全体参照

モデル全体からフィールドへの矢印。

```yaml
lineage:
  - from: HttpRequest
    to: UserDomain.AddressValueObject.zipCode
    transform: "extract from request"
```

## パターン8: 複数ソース（配列形式）

```yaml
lineage:
  - from: [sales.amount]
    to: daily_summary.total_amount
    transform: "sum group_by: customer_id, order_date"
```
