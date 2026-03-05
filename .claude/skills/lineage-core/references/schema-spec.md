# lineage-v1 スキーマ仕様

## トップレベル構造

```yaml
spec: lineage-v1       # 必須: バージョン識別子
models: [...]          # 任意: モデル定義の配列（CSV/API使用時は空可）
lineage: [...]         # 必須: エッジ定義の配列（最低1つ）
```

## モデル定義

```yaml
models:
  - name: ModelName      # 必須: モデル名（Mermaidサブグラフのタイトル）
    type: program        # 必須: "program"（処理層・青）または "datastore"（永続化層・緑）
    props: [field1, field2]  # 任意: フィールド名の配列（省略時はlineageから動的生成）
    children:            # 任意: 子モデルの配列（再帰構造）
      - name: ChildModel
        type: program
        props: [childField1]
```

### type の意味

| type | 用途 | Mermaid表示 |
|------|------|------------|
| `program` | DTO, Entity, ValueObject, API Request/Response | 青背景 |
| `datastore` | テーブル, ビュー, ファイル, キュー | 緑背景 |

### props の省略

`props` を省略すると、lineage の `from`/`to` で参照されたフィールドが自動的にプロパティとして追加される。
階層構造（`Parent.Child.field`）の場合、未定義の子モデルも自動作成される。

## lineage エッジ定義

```yaml
lineage:
  - from: Source.field        # 必須: ソース参照
    to: Target.field          # 必須: ターゲット参照
    transform: "変換ロジック"   # 任意: 変換の説明
```

### from/to の参照形式

| 形式 | 意味 | 例 |
|------|------|-----|
| `Model.field` | フィールド参照 | `UserDto.name` |
| `Parent.Child.field` | 階層フィールド参照 | `Domain.ValueObject.amount` |
| `Model#instance.field` | インスタンスフィールド | `Money#jpy.amount` |
| `Model` | モデル全体参照 | `HttpRequest` |
| `Model#instance` | インスタンス全体参照 | `Money#jpy` |
| リテラル文字列 | 固定値 | `JP`, `now()`, `v1.0` |

### from の配列形式

複数ソースからの変換は配列で表現:

```yaml
- from: [sales.quantity, sales.price]
  to: sales.total_amount
  transform: "quantity * price"
```

## 外部モデルソース

### CSV ファイル

- ファイル名規則: `論理名__物理名.csv`
- CLI: `--program-model-dir DIR` / `--datastore-model-dir DIR`
- 2列目（物理名）がプロパティ名として使用される

### OpenAPI 3.x

- `components/schemas` からモデル定義を抽出
- CLI: `--openapi-spec FILE`

### AsyncAPI 3.x

- `components/schemas` からモデル定義を抽出（`$ref` 解決、`allOf` マージ対応）
- CLI: `--asyncapi-spec FILE`

## 判定優先順序

lineage の `from`/`to` 値は以下の順序で判定:

1. **モデル参照**: `models` に登録されているモデル名と一致 → サブグラフ全体
2. **フィールド参照**: `Model.field` 形式で既知のフィールドと一致 → 特定ノード
3. **リテラル値**: 上記以外 → 動的生成されるリテラルノード
