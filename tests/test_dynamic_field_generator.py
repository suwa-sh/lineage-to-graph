"""
DynamicFieldGeneratorクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import DynamicFieldGenerator, Models, ModelDefinition, LineageEntries, LineageEntry


class TestDynamicFieldGenerator:
    """DynamicFieldGeneratorクラスのテスト"""

    # generateメソッドのテスト

    def test_generate_インスタンス記法の場合_フィールドが生成されること(self):
        # Given: インスタンス記法(#)を含むlineage
        models = Models([
            ModelDefinition("Money", "program", (), ())
        ])
        lineage = LineageEntries([
            LineageEntry(("literal",), "Money#jpy.amount", None),
            LineageEntry(("literal",), "Money#usd.currency", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: インスタンス記法から正しくフィールドが抽出される
        money = result.find_by_name("Money")
        assert money is not None
        assert "amount" in money.props
        assert "currency" in money.props

    def test_generate_親モデルの型が継承されること(self):
        # Given: 階層構造で親モデルがdatastore型
        models = Models([
            ModelDefinition("ParentDB", "datastore", (), ())
        ])
        lineage = LineageEntries([
            LineageEntry(("literal",), "ParentDB.ChildTable.id", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 子モデルが親の型(datastore)を継承する
        parent = result.find_by_name("ParentDB")
        assert parent is not None
        assert len(parent.children) == 1
        assert parent.children[0].name == "ChildTable"
        assert parent.children[0].type == "datastore"  # 親の型を継承
        assert "id" in parent.children[0].props

    def test_generate_複数階層の動的生成_順序が保持されること(self):
        # Given: 既存の子モデルと動的生成される子モデル
        models = Models([
            ModelDefinition(
                "Parent",
                "program",
                (),
                (
                    ModelDefinition("ExistingChild1", "program", ("field1",), ()),
                    ModelDefinition("ExistingChild2", "program", ("field2",), ())
                )
            )
        ])
        lineage = LineageEntries([
            # 既存の子の順序: ExistingChild1, ExistingChild2
            # 新規の子を追加
            LineageEntry(("literal",), "Parent.NewChild.newField", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 元の子の順序が保持され、新規の子は末尾に追加される
        parent = result.find_by_name("Parent")
        assert parent is not None
        assert len(parent.children) == 3
        assert parent.children[0].name == "ExistingChild1"
        assert parent.children[1].name == "ExistingChild2"
        assert parent.children[2].name == "NewChild"
        assert "newField" in parent.children[2].props

    def test_generate_既存モデルと動的モデル混在_正しく統合されること(self):
        # Given: 既存propsを持つモデルと空propsのモデル
        models = Models([
            ModelDefinition("ModelWithProps", "program", ("existing1", "existing2"), ()),
            ModelDefinition("ModelWithoutProps", "program", (), ())
        ])
        lineage = LineageEntries([
            LineageEntry(("literal",), "ModelWithProps.existing1", None),  # 既存フィールドへの参照
            LineageEntry(("literal",), "ModelWithoutProps.dynamic1", None),  # 動的生成
            LineageEntry(("literal",), "ModelWithoutProps.dynamic2", None)   # 動的生成
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 既存propsは変更されず、空propsのみ動的生成される
        with_props = result.find_by_name("ModelWithProps")
        without_props = result.find_by_name("ModelWithoutProps")

        assert with_props is not None
        assert set(with_props.props) == {"existing1", "existing2"}  # 変更なし

        assert without_props is not None
        assert "dynamic1" in without_props.props  # 動的生成
        assert "dynamic2" in without_props.props  # 動的生成

    def test_generate_フィールド参照でない場合_スキップされること(self):
        # Given: フィールド参照でないlineageエントリ
        models = Models([
            ModelDefinition("TargetModel", "program", (), ())
        ])
        lineage = LineageEntries([
            # ドット無し（モデル全体参照）
            LineageEntry(("literal",), "TargetModel", None),
            # 存在しないモデル（リテラルとして扱われる）
            LineageEntry(("UndefinedModel.field",), "TargetModel.realField", None),
            # 複数ドットだが不正な形式
            LineageEntry(("invalid..format",), "TargetModel.realField", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 有効なフィールド参照のみが生成される
        target = result.find_by_name("TargetModel")
        assert target is not None
        assert set(target.props) == {"realField"}  # realFieldのみ

    # immutableのテスト

    def test_generate_新しいModelsインスタンスが返されること(self):
        # Given: ModelsとLineageEntries
        models = Models([
            ModelDefinition("Model1", "program", (), ())
        ])
        lineage = LineageEntries([
            LineageEntry(("literal",), "Model1.field1", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 新しいModelsインスタンスが返される
        assert result is not models
        assert isinstance(result, Models)

    def test_generate_元のModelsが変更されないこと(self):
        # Given: ModelsとLineageEntries
        original_model = ModelDefinition("Model1", "program", (), ())
        models = Models([original_model])
        lineage = LineageEntries([
            LineageEntry(("literal",), "Model1.newField", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 元のモデルは変更されない
        original_from_models = models.find_by_name("Model1")
        assert original_from_models is not None
        assert len(original_from_models.props) == 0  # 元は空のまま

        updated = result.find_by_name("Model1")
        assert updated is not None
        assert "newField" in updated.props  # 結果には追加されている

    # _extract_field_referenceのエッジケーステスト

    def test_generate_インスタンス記法で不正な形式の場合_スキップされること(self):
        # Given: インスタンス記法だが不正な形式（フィールドなし）
        models = Models([
            ModelDefinition("Money", "program", (), ())
        ])
        lineage = LineageEntries([
            # インスタンス記法だがドットがない（Model#instanceのみ）
            LineageEntry(("Money#jpy",), "Money.realField", None),
            # 正常なエントリ
            LineageEntry(("literal",), "Money.realField", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 不正な形式はスキップされ、正常なフィールドのみ生成される
        money = result.find_by_name("Money")
        assert money is not None
        assert set(money.props) == {"realField"}

    def test_generate_ドット区切りが不正な場合_スキップされること(self):
        # Given: ドット区切りが不正な形式
        models = Models([
            ModelDefinition("Target", "program", (), ())
        ])
        lineage = LineageEntries([
            # 単一要素（ドットなし）
            LineageEntry(("NoDotsAtAll",), "Target.field1", None),
            # 正常なエントリ
            LineageEntry(("literal",), "Target.field1", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 不正な形式はスキップされる
        target = result.find_by_name("Target")
        assert target is not None
        assert set(target.props) == {"field1"}

    def test_generate_すべてのパーツが既存の場合_早期リターンされること(self):
        # Given: 既に完全に定義された階層構造
        models = Models([
            ModelDefinition(
                "Parent",
                "program",
                ("p_field",),
                (ModelDefinition("ExistingChild", "program", ("c_field",), ()),)
            )
        ])
        lineage = LineageEntries([
            # 既存の子モデルへの参照（新規作成不要）
            LineageEntry(("literal",), "Parent.ExistingChild.c_field", None)
        ])
        generator = DynamicFieldGenerator(models, lineage)

        # When: generateを呼ぶ
        result = generator.generate()

        # Then: 既存の構造が維持される（新規作成されない）
        parent = result.find_by_name("Parent")
        assert parent is not None
        assert len(parent.children) == 1
        assert parent.children[0].name == "ExistingChild"
