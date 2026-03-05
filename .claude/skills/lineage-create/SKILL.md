---
name: lineage-create
description: データモデル定義やコードのエントリーポイントからlineage-v1形式のYAML定義を新規作成します。CSV、OpenAPI、AsyncAPI、コード内の型定義などからソース/ターゲットのモデルとフィールドマッピングを推測して生成します。「lineage定義を作成」「リネージを新規作成」「データフローを定義」などのキーワードで発動します。
argument-hint: <エントリーポイントのファイルパス、またはデータモデルの説明>
---

# lineage定義の新規作成

データモデル定義やエントリーポイントから lineage-v1 形式の YAML 定義を生成するスキルです。

## 前提条件

- lineage-to-graph がセットアップ済みであること（未セットアップの場合は `lineage-setup` スキルを案内）

## 共有リソース

- スキーマ仕様: `../lineage-core/references/schema-spec.md`
- YAMLパターン集: `../lineage-core/references/yaml-patterns.md`
- 変換スクリプト: `../lineage-core/scripts/lineage_to_md.py`

## 出力先

生成したファイルはプロジェクトルートの `docs/lineages/` に配置する（デフォルト）。
ユーザーが別のディレクトリを指定した場合はそちらに従う。

```
<project-root>/
└── docs/
    └── lineages/
        ├── <name>.yml    # lineage定義
        └── <name>.md     # 生成されたMermaid図
```

ディレクトリが存在しない場合は作成する。

## ワークフロー

### Step 1: 入力情報の収集

ユーザーから以下の情報を収集する:

1. **エントリーポイント**: データフローの起点となるファイルやモデル定義
   - ファイルパス（コード、CSV、OpenAPI/AsyncAPI仕様）
   - またはテキストによるモデル説明
2. **データフローの方向**: ソース → ターゲットの概要
3. **モデルの種類**: program（処理層）か datastore（永続化層）か
4. **出力先**: lineage定義とMermaid図の出力ディレクトリ（デフォルト: `docs/lineages/`）

### Step 2: データモデルの解析

入力に応じて、以下のいずれかの方法でモデル情報を抽出する:

**A. コード内の型定義から（TypeScript, Java, Python, etc.）:**
- クラス/インターフェース/型定義からプロパティ名を抽出
- コンストラクタやファクトリメソッドの引数も参考にする

**B. CSV定義から:**
- ファイル名規則: `論理名__物理名.csv`
- 2列目（物理名）がプロパティ名になる
- `--program-model-dir` / `--datastore-model-dir` オプションで指定

**C. OpenAPI/AsyncAPI仕様から:**
- `components/schemas` からモデル定義を抽出
- `--openapi-spec` / `--asyncapi-spec` オプションで指定

**D. テキスト説明から:**
- ユーザーの説明からモデル名とプロパティを推測

### Step 3: lineage YAML の生成

収集した情報から lineage-v1 形式の YAML を生成する。

生成時の判断基準:
- **同名フィールド**: そのままマッピング（transform なし）
- **名前が異なるフィールド**: transform に変換ロジックを記述
- **固定値**: リテラルとして `from` に直接記述
- **計算フィールド**: 複数ソースの場合は配列形式の `from` を使用
- **階層構造**: ValueObject等のネストは `children` と `Parent.Child.field` 記法を使用
- **propsの省略**: フィールドが不明確な場合は props を省略し、lineage参照から動的生成に任せる

YAML パターンの詳細は `../lineage-core/references/yaml-patterns.md` を参照。
スキーマ仕様の詳細は `../lineage-core/references/schema-spec.md` を参照。

### Step 4: ファイル出力

生成した YAML を出力ディレクトリに保存する:

```bash
# 出力ディレクトリの作成
mkdir -p docs/lineages

# YAMLファイルの保存
# ファイル名はデータフローを表す名前にする（例: http-request-to-transaction.yml）
```

### Step 5: 検証

生成した YAML を `../lineage-core/scripts/lineage_to_md.py` で検証する:

```bash
# Markdown + Mermaid図への変換（出力も同じディレクトリに配置）
python3 ../lineage-core/scripts/lineage_to_md.py docs/lineages/<name>.yml docs/lineages/<name>.md [options]

# Mermaid構文チェック
npx md-mermaid-lint docs/lineages/<name>.md
```

変換エラーや構文エラーがあれば修正する。

### Step 6: 結果の提示

以下をユーザーに提示する:

1. 生成した YAML ファイルのパス
2. 生成された Mermaid 図（Markdownファイルの内容）
3. 変換コマンド（再実行用）
4. 修正が必要な箇所があれば指摘

## 注意事項

- CSV や API仕様を使う場合は、対応する CLI オプションを付与する
- 大規模なモデル（50+フィールド）の場合は、props を省略して動的生成に任せることを提案する
