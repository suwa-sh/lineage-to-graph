---
name: lineage-core
description: lineage-to-graph の共有リソースを提供する内部スキルです。他のlineage系スキル（lineage-create, lineage-to-code, code-to-lineage）から参照されます。直接トリガーされることは想定していません。
---

# lineage-core: 共有リソース

このスキルは他の lineage 系スキルから参照される共有リソースを提供します。

## 提供するリソース

### references/

- **schema-spec.md**: lineage-v1 スキーマ仕様（モデル定義、lineageエッジ定義、参照形式）
- **yaml-patterns.md**: lineage YAML パターン集（基本マッピング、階層構造、インスタンス、ETL等）
- **lineage-reading-guide.md**: lineage定義の読み方ガイド（コード生成時の解釈方法）

### scripts/

- **lineage_to_md.py**: lineage-to-graph 本体スクリプト（YAML → Markdown+Mermaid変換）
- **requirements.txt**: Python依存パッケージ

## 他のスキルからの参照方法

各スキルの SKILL.md 内で以下のように参照:

```
スキーマ仕様は ../lineage-core/references/schema-spec.md を参照してください。
変換スクリプトは ../lineage-core/scripts/lineage_to_md.py を使用してください。
```
