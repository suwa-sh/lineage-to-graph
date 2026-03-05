---
name: lineage-to-code
description: lineage-v1形式のYAML定義を読み取り、プロジェクトのコンテキスト（言語、フレームワーク、既存コード）に合わせたマッピング実装コードを生成します。「lineageから実装」「リネージ定義をコードに変換」「マッピングコードを生成」「lineage定義に従って実装」などのキーワードで発動します。
argument-hint: <lineage定義ファイルのパス>
---

# lineage定義から実装コード生成

lineage-v1 YAML 定義を読み取り、プロジェクトの規約に従ったマッピング実装コードを生成するスキルです。

## 共有リソース

- lineage定義の読み方: `../lineage-core/references/lineage-reading-guide.md`
- スキーマ仕様: `../lineage-core/references/schema-spec.md`

## ワークフロー

### Step 1: lineage定義の読み込み

`$ARGUMENTS` またはユーザー指示からlineage定義ファイルを読み込む。

lineage定義の読み方は `../lineage-core/references/lineage-reading-guide.md` を参照。

### Step 2: プロジェクトコンテキストの収集

以下を調査してプロジェクトの規約を把握する:

1. **言語・フレームワーク**: package.json, pom.xml, build.gradle, pyproject.toml 等から特定
2. **既存のマッピングパターン**: プロジェクト内に既存のマッパー/コンバーター/トランスフォーマーがあれば、そのパターンに従う
3. **モデルクラスの位置**: lineage定義に登場するモデル名に対応するクラス/型定義を探す
4. **命名規則**: camelCase/snake_case/PascalCase 等
5. **テストパターン**: 既存テストの書き方を確認

### Step 3: マッピングコードの生成

lineage定義の各エッジに対応する実装コードを生成する。

**生成の指針:**

- lineage の `from` → `to` が1つのフィールド代入に対応
- `transform` がある場合は変換ロジックを実装
- リテラル値（`JP`, `now()` 等）は定数やユーティリティ呼び出しに変換
- 複数ソース（`from` が配列）は計算ロジックとして実装
- モデル全体参照はオブジェクトレベルのマッピングとして実装

**言語別の典型的な実装パターン:**

| lineage定義 | TypeScript | Java | Python |
|------------|------------|------|--------|
| `from: A.x, to: B.x` | `b.x = a.x` | `b.setX(a.getX())` | `b.x = a.x` |
| `from: A.x, to: B.y, transform: toUpper` | `b.y = a.x.toUpperCase()` | `b.setY(a.getX().toUpperCase())` | `b.y = a.x.upper()` |
| `from: JP, to: B.country` | `b.country = 'JP'` | `b.setCountry("JP")` | `b.country = "JP"` |
| `from: [A.x, A.y], to: B.z, transform: x*y` | `b.z = a.x * a.y` | `b.setZ(a.getX() * a.getY())` | `b.z = a.x * a.y` |

### Step 4: 階層構造の処理

lineage定義に `Parent.Child.field` 形式の参照がある場合:

1. 親モデルと子モデルの関係を確認
2. 子モデルのインスタンス生成コードも含める
3. 親モデルへの子モデル設定コードも含める

### Step 5: テストコードの生成

生成したマッピングコードに対するテストも生成する:

- lineage定義の各エッジがテストケースに対応
- リテラル値のテストケース
- transform の変換ロジックのテストケース

### Step 6: 結果の提示

以下をユーザーに提示する:

1. 生成したマッピングコード
2. 生成したテストコード
3. lineage定義との対応表（どのエッジがどのコードに対応するか）
4. 手動で確認・調整が必要な箇所

## 注意事項

- プロジェクトの既存パターンを最優先で踏襲する
- lineage定義にない処理（バリデーション、エラーハンドリング等）はプロジェクトの規約に従って追加する
- `transform` の記述は自然言語のヒントであり、正確な実装はプロジェクトのコンテキストから判断する
