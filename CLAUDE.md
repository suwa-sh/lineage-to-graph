# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

`lineage-to-graph` は、YAML/JSON形式で定義したカラム単位のデータリネージ情報を、Markdown + Mermaid図へ自動変換するツールです。

## セットアップ

### 必須環境
- Python 3.8+

### 依存関係のインストール
```bash
pip install -r requirements.txt
```

または直接インストール:
```bash
pip install PyYAML
```

## 基本的なコマンド

### リネージ変換の実行
```bash
python lineage_to_md.py data/sample.yml data/output/output.md

# lint
md-mermaid-lint data/output/output.md                                    
```

### スキーマバリデーション（オプション）
```bash
pip install jsonschema
jsonschema -i data/sample.yml schema.json
```

## アーキテクチャ

### コア変換ロジック ([lineage_to_md.py](lineage_to_md.py))

このプロジェクトは単一のPythonスクリプトで構成されており、以下の3つの主要フェーズで動作します:

1. **モデル解析フェーズ** ([lineage_to_md.py:26-36](lineage_to_md.py#L26-L36))
   - YAMLの`models`セクションからモデル名、タイプ(`program`/`datastore`)、プロパティを抽出
   - 各フィールドのMermaidノードID(`{model}_{field}`形式)を生成し、`field_node_ids`辞書に格納
   - モデルごとのフィールドリストを`field_nodes_by_model`に保存

2. **Mermaidサブグラフ生成フェーズ** ([lineage_to_md.py:47-54](lineage_to_md.py#L47-L54))
   - モデルごとにMermaidサブグラフを生成
   - フィールドをサブグラフ内のノードとして配置
   - タイプに応じたCSSクラス(`program`/`datastore`)を適用

3. **リネージエッジ生成フェーズ** ([lineage_to_md.py:68-82](lineage_to_md.py#L68-L82))
   - `lineage`配列の各エントリを処理
   - `from`が`Model.field`形式の場合は既存ノードIDを使用
   - それ以外(リテラル値)の場合は`ensure_literal()`でリテラルノードを動的生成
   - `transform`プロパティがあればエッジラベルとして表示

### ノードID生成ルール ([lineage_to_md.py:4-12](lineage_to_md.py#L4-L12))

`slug()`関数は安全なMermaid識別子を生成します:
- `::` は `_` に変換
- 英数字とアンダースコア以外を `_` に変換
- 連続するアンダースコアを1つにまとめる
- 数字で始まる場合は `n_` をプレフィックス

### リテラル値とフィールド参照の区別

リネージの`from`値は以下のように解釈されます:
- **ドット(`.`)を含む場合**: `Model.field`形式のフィールド参照として扱う ([lineage_to_md.py:65-66](lineage_to_md.py#L65-L66))
- **ドット(`.`)を含まない場合**: リテラル値(例: `JP`, `now()`)として扱い、専用のリテラルノードを生成 ([lineage_to_md.py:56-63](lineage_to_md.py#L56-L63))

### スキーマ仕様 ([schema.json](schema.json))

JSON Schemaは以下を定義:
- `spec: "lineage-v1"` - バージョン識別子(必須)
- `models` - モデル定義の配列(name, type, propsが必須)
- `lineage` - エッジ定義の配列(from, toが必須、transformはオプション)
- `from`は文字列または配列が可能
- `to`は必ず`Model.field`形式のパターンを強制

## 階層構造のサポート

### 概要

モデルを入れ子にして階層構造を表現できます。DomainモデルにValueObjectを含める場合などに使用します。

### スキーマ定義

[schema.json](schema.json) の `models[].children` プロパティを使用:

```yaml
models:
  - name: TransactionDomain
    type: program
    props: [id, userId, createdAt]
    children:
      - name: MoneyValueObject
        type: program
        props: [amount, currency]
      - name: MetadataValueObject
        type: program
        props: [source, version]
```

### フィールド参照記法

階層構造のフィールドは `Parent.Child.field` 形式で参照:

```yaml
lineage:
  - from: HttpRequest.amount
    to: TransactionDomain.MoneyValueObject.amount
  - from: JP
    to: TransactionDomain.MoneyValueObject.currency
```

### Mermaid出力

入れ子サブグラフとして出力されます:

```mermaid
subgraph TransactionDomain[TransactionDomain]
  TransactionDomain_id["id"]:::property

  subgraph TransactionDomain_MoneyValueObject[MoneyValueObject]
    TransactionDomain_MoneyValueObject_amount["amount"]:::property
    TransactionDomain_MoneyValueObject_currency["currency"]:::property
  end
end
```

### 実装詳細

- **再帰的パース** ([lineage_to_md.py:33-91](lineage_to_md.py#L33-L91))
  - `parse_models_recursive()` が親子関係を辿ってモデル階層を構築
  - 親のプレフィックスを子に伝播 (`Parent.Child` 形式)
  - フィールドIDを `{parent}_{child}_{field}` で生成

- **入れ子サブグラフ生成** ([lineage_to_md.py:93-140](lineage_to_md.py#L93-L140))
  - `generate_subgraph()` がインデントレベルを管理
  - 子モデルを親サブグラフ内に再帰的に配置

### サンプル

実際の使用例は [data/event-driven.yml](data/event-driven.yml) を参照してください。

## CSVからのモデル読み込み (v3.0+)

### 概要

モデル定義をCSVファイルから読み込むことができます。大規模なデータモデルをCSVで管理しつつ、リネージ定義はYAMLで簡潔に記述できます。

### CSV形式

**ファイル名規則**: `論理名__物理名.csv`
- 例: `HTTPリクエスト__HttpRequest.csv`
- 例: `残高__balance_snapshot.csv`

**CSV列定義**:
```csv
論理名,物理名,データ型,サイズ,キー,説明
```
- **program系**: 最初の3列(論理名,物理名,データ型)
- **datastore系**: 全6列

**使用される列**:
- `物理名`: propsリストの要素として使用
- その他の列: 現在は未使用(将来的にメタデータとして活用可能)

### コマンドライン引数

```bash
python lineage_to_md.py <input.yaml> <output.md> \
  --program-model-dirs <dir1> <dir2> ... \
  --datastore-model-dirs <dir1> <dir2> ...
```

**引数**:
- `--program-model-dirs`: programタイプのモデルCSVが格納されたディレクトリ(複数指定可)
- `--datastore-model-dirs`: datastoreタイプのモデルCSVが格納されたディレクトリ(複数指定可)

### 使用パターン

#### パターン1: 完全CSV方式
```yaml
# lineage.yml
spec: lineage-v1
models: []  # 空でOK

lineage:
  - from: HttpRequest.amount
    to: balance_snapshot.total_amount
```

```bash
python lineage_to_md.py lineage.yml output.md \
  --program-model-dirs data/レイアウト \
  --datastore-model-dirs data/テーブル定義
```

#### パターン2: YAML + CSV混在方式
```yaml
# lineage.yml
spec: lineage-v1
models:
  # 階層構造はYAMLで定義
  - name: TransactionDomain
    type: program
    props: [id, userId]
    children:
      - name: MoneyValueObject
        type: program
        props: [amount, currency]

lineage:
  - from: HttpRequest.amount  # ← CSVから読み込み
    to: TransactionDomain.MoneyValueObject.amount
```

#### パターン3: 完全YAML方式(既存互換)
```yaml
# 従来通り、すべてYAMLに定義
spec: lineage-v1
models: [...]
lineage: [...]
```

```bash
# --model-dirs不要
python lineage_to_md.py sample.yml output.md
```

### 実装詳細

- **CSV読み込み** ([lineage_to_md.py:19-83](lineage_to_md.py#L19-L83))
  - `load_model_from_csv()`: CSVファイルを読み込んでモデル定義を返す
  - ファイル名から物理名(モデル名)を抽出
  - エンコーディング自動判定(UTF-8 → CP932 → Shift_JIS)

- **モデル探索** ([lineage_to_md.py:119-166](lineage_to_md.py#L119-L166))
  - `find_model_csvs()`: 指定ディレクトリから必要なモデルCSVを探索
  - `**/*.csv`パターンで再帰的に検索

- **参照モデル抽出** ([lineage_to_md.py:85-117](lineage_to_md.py#L85-L117))
  - `extract_referenced_models()`: lineageから参照されているモデル名を抽出

- **統合ロジック** ([lineage_to_md.py:293-345](lineage_to_md.py#L293-L345))
  - YAML定義のモデルを優先
  - 不足分をCSVから補完
  - 重複チェックと警告メッセージ

### サンプル

実際の使用例は [data/lineage_csv_example.yml](data/lineage_csv_example.yml) を参照してください。

## 実装時の注意点

### 新機能追加時
- `slug()`関数を使用してMermaid識別子を生成し、構文エラーを防ぐ
- `field_node_ids`辞書を使用して既存フィールド参照を解決
- リテラル値は`ensure_literal()`で重複を避けながら動的生成
- 新しいモデルタイプを追加する場合はCSSクラス定義も追加 ([lineage_to_md.py:41-43](lineage_to_md.py#L41-L43))

### スキーマ拡張時
- [schema.json](schema.json) の`enum`値を更新(例: 新しい`type`)
- `examples`セクションに使用例を追加して検証可能にする
