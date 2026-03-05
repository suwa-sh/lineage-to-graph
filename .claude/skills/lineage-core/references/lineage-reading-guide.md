# lineage定義の読み方

## YAML構造の概要

```yaml
spec: lineage-v1
models: [...]   # ソース/ターゲットのモデル定義
lineage: [...]  # フィールド間のマッピング（エッジ）
```

## models の読み方

各モデルは以下の情報を持つ:

- **name**: モデル名。コード内のクラス/テーブル名に対応
- **type**: `program`（処理層: DTO, Entity, VO）または `datastore`（永続化層: テーブル, ビュー）
- **props**: フィールド名の配列
- **children**: 子モデル（ValueObject等）の配列

### 階層構造の読み方

```yaml
- name: TransactionDomain
  type: program
  props: [id, userId]
  children:
    - name: MoneyValueObject
      type: program
      props: [amount, currency]
```

→ `TransactionDomain` クラスが `MoneyValueObject` を内包する構造。
→ lineageでは `TransactionDomain.MoneyValueObject.amount` として参照。

## lineage の読み方

各エントリは「from → to」のデータフローを表す。

### 参照形式の判定

| 形式 | 意味 | コードへの変換 |
|------|------|-------------|
| `Model.field` | 特定フィールド | `model.field` へのアクセス |
| `Parent.Child.field` | 階層フィールド | `parent.child.field` へのアクセス |
| `Model#instance.field` | インスタンスフィールド | 名前付きインスタンスの特定フィールド |
| `Model` | モデル全体 | オブジェクト全体の参照 |
| リテラル（ドットなし） | 固定値 | 定数、関数呼び出し |

### transform の解釈

`transform` はデータ変換の意図を自然言語で表現したもの:

| transform例 | 実装の方向性 |
|-------------|------------|
| `toUpperCase` | 文字列の大文字変換 |
| `cast to date` | 日付型への変換 |
| `lookup product master` | マスタテーブルとの結合 |
| `quantity * price` | 算術演算 |
| `sum group_by: X` | 集約関数 |
| `coalesce(X, 0)` | NULL安全な値取得 |
| `join dim_date on date` | ディメンションテーブルとの結合 |
| デフォルト値 | デフォルト値の設定 |

### 複数ソースの読み方

```yaml
- from: [raw.quantity, raw.price]
  to: stg.total_price
  transform: "quantity * price"
```

→ `quantity` と `price` の両方を入力として `total_price` を計算する。

## データフロー全体の把握方法

1. **models セクション**から全モデルとそのフィールドを一覧化
2. **lineage セクション**のエッジを追って、データの流れを左→右に把握
3. `type: program` のモデルは処理層（変換ロジックがある）
4. `type: datastore` のモデルは永続化層（最終的な保存先）
5. リテラル値は外部から注入される固定値

## モデルインスタンスの読み方

```yaml
- from: HttpRequest.amount_jpy
  to: Money#jpy.amount
```

`Money#jpy` は `Money` モデルの `jpy` という名前付きインスタンス。
同じモデルを異なるコンテキスト（通貨単位等）で複数回使用する場合に使う。
