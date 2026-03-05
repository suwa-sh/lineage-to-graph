---
name: code-to-lineage
description: 既存の実装コードを解析し、コールスタックをたどってlineage-v1形式のYAML定義を逆引き生成します。エントリーポイント（ファイルパス、関数/メソッド名）を指定すると、データの流れを追跡してlineage定義を作成します。「コードからlineage」「実装からリネージ」「データフローを逆引き」「リネージをリバース」などのキーワードで発動します。
argument-hint: <エントリーポイントのファイルパス:関数名>
---

# 実装コードからlineage定義を生成

既存の実装コードを解析し、コールスタックをたどってlineage-v1形式のYAML定義を逆引き生成するスキルです。

## 共有リソース

- スキーマ仕様: `../lineage-core/references/schema-spec.md`
- YAMLパターン集: `../lineage-core/references/yaml-patterns.md`
- 変換スクリプト: `../lineage-core/scripts/lineage_to_md.py`

## 前提条件

- lineage-to-graph がセットアップ済みであること
- 解析対象のコードベースにアクセスできること

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

### Step 1: エントリーポイントの特定

ユーザーから以下を受け取る:

1. **ファイルパス**: 解析の起点となるファイル
2. **関数/メソッド名**: 解析の起点となる関数（任意）
3. **スコープ**: どこまで追跡するか（デフォルト: 呼び出し先の末端まで）
4. **出力先**: lineage定義とMermaid図の出力ディレクトリ（デフォルト: `docs/lineages/`）

### Step 2: プロジェクト構造の把握

以下を調査する:

1. **言語・フレームワーク**: ビルド設定ファイルから特定
2. **アーキテクチャパターン**: レイヤードアーキテクチャ、ヘキサゴナル等
3. **命名規則**: Mapper, Converter, Transformer 等のパターン
4. **モデルクラスの配置**: entities/, models/, domain/, dto/ 等

### Step 3: コールスタックの追跡

エントリーポイントから以下の手順でデータフローを追跡する:

1. **入力モデルの特定**: メソッド引数やリクエストオブジェクトから入力モデルを特定
2. **フィールドアクセスの追跡**: 各フィールドがどこに代入されるかを追跡
3. **変換処理の検出**: 変換関数やロジックを `transform` として記録
4. **呼び出し先の探索**: メソッド呼び出しを追って、データの流れを末端まで追跡
5. **出力モデルの特定**: 最終的にデータが書き込まれるモデル/テーブルを特定

### 追跡時の注意点

**追跡対象:**
- フィールドの代入（`target.x = source.y`）
- コンストラクタ引数（`new Entity(source.x, source.y)`）
- ビルダーパターン（`builder.setX(source.x).setY(source.y)`）
- マッパー/コンバーター呼び出し
- データベースへの書き込み（INSERT/UPDATE）
- メッセージの発行（イベント、キュー）

**追跡を止めるポイント:**
- 外部サービスへの通信（API呼び出し）
- データベースの読み込み（SELECT）→ 新しいソースモデルの起点
- ファイルI/O

### Step 4: モデルとフィールドの整理

追跡結果から以下を整理する:

1. **モデル一覧**: 検出した全モデルを `program` / `datastore` に分類
2. **フィールド一覧**: 各モデルのフィールドを列挙
3. **データフロー**: from → to のマッピングを整理
4. **変換ロジック**: 各マッピングに対応する transform を整理
5. **階層構造**: ValueObject 等のネスト関係を children として構造化

### Step 5: lineage YAML の生成と出力

整理した情報を lineage-v1 形式のYAMLに変換し、出力ディレクトリに保存する。

```bash
# 出力ディレクトリの作成
mkdir -p docs/lineages

# ファイル名はエントリーポイントや処理内容を表す名前にする
# 例: create-transaction.yml, user-registration.yml
```

生成ルールの詳細は `../lineage-core/references/schema-spec.md` を参照。
パターン例は `../lineage-core/references/yaml-patterns.md` を参照。

### Step 6: 検証

`../lineage-core/scripts/lineage_to_md.py` で検証する:

```bash
# 変換実行（出力も同じディレクトリに配置）
python3 ../lineage-core/scripts/lineage_to_md.py docs/lineages/<name>.yml docs/lineages/<name>.md [options]

# Mermaid構文チェック
npx md-mermaid-lint docs/lineages/<name>.md
```

### Step 7: ユーザーレビュー

以下をユーザーに提示する:

1. 生成した lineage YAML ファイルのパス
2. 生成された Mermaid 図
3. 追跡したコールスタックの概要
4. 判断に迷った箇所（複数の解釈が可能な変換等）
5. 追跡できなかった箇所（外部サービス呼び出し等）

## 注意事項

- コードベースが大きい場合は、段階的に追跡する（まず1つのユースケースから）
- フレームワーク固有のマジック（DI、AOP、リフレクション）は追跡が難しい場合がある。その場合はユーザーに確認する
- 既存のlineage定義がある場合は、差分のみ追加する方針を確認する
- 推測が入る箇所は `transform` にコメントとして明記する
