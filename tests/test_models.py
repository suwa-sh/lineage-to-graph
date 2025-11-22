"""
Modelsクラスのunit test

複合条件カバレッジ: 主要パスを網羅
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import Models, ModelDefinition, LineageEntries, LineageEntry


class TestModels:
    """Modelsクラスのテスト"""

    # find_by_nameメソッドのテスト

    def test_find_by_name_モデルが存在する場合_モデル定義が返されること(self):
        # Given: 複数のモデルを持つModels
        models = Models([
            ModelDefinition("User", "program", ["id", "name"], []),
            ModelDefinition("Product", "datastore", ["id", "price"], [])
        ])

        # When: 存在するモデル名で検索
        result = models.find_by_name("User")

        # Then: モデル定義が返される
        assert result is not None
        assert result.name == "User"
        assert result.type == "program"

    def test_find_by_name_モデルが存在しない場合_Noneが返されること(self):
        # Given: モデルを持つModels
        models = Models([
            ModelDefinition("User", "program", ["id"], [])
        ])

        # When: 存在しないモデル名で検索
        result = models.find_by_name("NonExistent")

        # Then: Noneが返される
        assert result is None

    def test_find_by_name_空のModelsの場合_Noneが返されること(self):
        # Given: 空のModels
        models = Models([])

        # When: 任意のモデル名で検索
        result = models.find_by_name("AnyModel")

        # Then: Noneが返される
        assert result is None

    # get_namesメソッドのテスト

    def test_get_names_すべてのモデル名が返されること(self):
        # Given: 複数のモデルを持つModels
        models = Models([
            ModelDefinition("User", "program", [], []),
            ModelDefinition("Product", "datastore", [], []),
            ModelDefinition("Order", "program", [], [])
        ])

        # When: get_namesを呼ぶ
        result = models.get_names()

        # Then: すべてのモデル名がセットで返される
        assert result == {"User", "Product", "Order"}

    def test_get_names_空の場合_空のセットが返されること(self):
        # Given: 空のModels
        models = Models([])

        # When: get_namesを呼ぶ
        result = models.get_names()

        # Then: 空のセットが返される
        assert result == set()

    # to_listメソッドのテスト

    def test_to_list_すべてのモデルが返されること(self):
        # Given: 複数のモデルを持つModels
        model_list = [
            ModelDefinition("User", "program", [], []),
            ModelDefinition("Product", "datastore", [], [])
        ]
        models = Models(model_list)

        # When: to_listを呼ぶ
        result = models.to_list()

        # Then: すべてのモデルがリストで返される
        assert len(result) == 2
        assert result[0].name == "User"
        assert result[1].name == "Product"

    def test_to_list_防御的コピーが返されること(self):
        # Given: Models
        model_list = [ModelDefinition("User", "program", [], [])]
        models = Models(model_list)

        # When: to_listを呼ぶ
        result = models.to_list()

        # Then: リストのコピーが返される
        assert result == model_list
        assert result is not model_list

    # __iter__メソッドのテスト

    def test_iter_すべてのモデルをイテレートできること(self):
        # Given: 複数のモデルを持つModels
        model_list = [
            ModelDefinition("M1", "program", [], []),
            ModelDefinition("M2", "datastore", [], []),
            ModelDefinition("M3", "program", [], [])
        ]
        models = Models(model_list)

        # When: forループでイテレート
        result = list(models)

        # Then: すべてのモデルが取得できる
        assert len(result) == 3
        assert result == model_list

    # mergeメソッドのテスト

    def test_merge_複数のModelsが結合されること(self):
        # Given: 複数のModels
        models1 = Models([
            ModelDefinition("User", "program", [], [])
        ])
        models2 = Models([
            ModelDefinition("Product", "datastore", [], [])
        ])
        models3 = Models([
            ModelDefinition("Order", "program", [], [])
        ])

        # When: mergeを呼ぶ
        result = Models.merge([models1, models2, models3])

        # Then: すべてのモデルが結合される
        names = result.get_names()
        assert names == {"User", "Product", "Order"}

    def test_merge_空のリストの場合_空のModelsが返されること(self):
        # Given: 空のリスト
        models_list = []

        # When: mergeを呼ぶ
        result = Models.merge(models_list)

        # Then: 空のModelsが返される
        assert result.get_names() == set()

    def test_merge_重複するモデルがある場合_すべて含まれること(self):
        # Given: 同じモデル名を含む複数のModels
        models1 = Models([ModelDefinition("User", "program", ["id"], [])])
        models2 = Models([ModelDefinition("User", "datastore", ["name"], [])])

        # When: mergeを呼ぶ
        result = Models.merge([models1, models2])

        # Then: 両方のモデルが含まれる（重複チェックなし）
        assert len(result.to_list()) == 2

    # with_dynamic_fieldsメソッドのテスト

    def test_with_dynamic_fields_未定義モデルの動的生成_フィールドが生成されること(self):
        # Given: 空のpropsを持つモデルとlineage
        models = Models([
            ModelDefinition("Target", "program", [], [])
        ])
        lineage = LineageEntries([
            LineageEntry(["literal1"], "Target.field1", None),
            LineageEntry(["literal2"], "Target.field2", None)
        ])

        # When: with_dynamic_fieldsを呼ぶ
        result = models.with_dynamic_fields(lineage)

        # Then: 動的にフィールドが生成される
        target = result.find_by_name("Target")
        assert target is not None
        assert set(target.props) == {"field1", "field2"}

    def test_with_dynamic_fields_既存propsがある場合_動的生成されないこと(self):
        # Given: 既存propsを持つモデルとlineage
        models = Models([
            ModelDefinition("Target", "program", ["existingField"], [])
        ])
        lineage = LineageEntries([
            LineageEntry(["source"], "Target.newField", None)
        ])

        # When: with_dynamic_fieldsを呼ぶ
        result = models.with_dynamic_fields(lineage)

        # Then: 既存propsがある場合は動的フィールド生成は行われない
        target = result.find_by_name("Target")
        assert target is not None
        assert set(target.props) == {"existingField"}  # newFieldは追加されない

    def test_with_dynamic_fields_階層構造の動的生成_子モデルが生成されること(self):
        # Given: 空のpropsを持つ親モデルとネストしたlineage
        models = Models([
            ModelDefinition("Parent", "program", [], [])
        ])
        lineage = LineageEntries([
            LineageEntry(["source"], "Parent.Child.field", None)
        ])

        # When: with_dynamic_fieldsを呼ぶ
        result = models.with_dynamic_fields(lineage)

        # Then: 子モデルが動的に生成される
        parent = result.find_by_name("Parent")
        assert parent is not None
        assert len(parent.children) == 1
        assert parent.children[0].name == "Child"
        assert "field" in parent.children[0].props

    def test_with_dynamic_fields_モデル自体が未定義の場合_スキップされること(self):
        # Given: lineageに参照されているが未定義のモデル
        models = Models([
            ModelDefinition("ExistingModel", "program", [], [])
        ])
        lineage = LineageEntries([
            LineageEntry(["source"], "UndefinedModel.field", None)
        ])

        # When: with_dynamic_fields を呼ぶ
        result = models.with_dynamic_fields(lineage)

        # Then: 未定義モデルはスキップされる（警告メッセージのみ）
        assert result.find_by_name("UndefinedModel") is None
        assert result.find_by_name("ExistingModel") is not None

    # immutableのテスト

    def test_immutable_frozenであること(self):
        # Given: Models
        models = Models([ModelDefinition("User", "program", [], [])])

        # When/Then: frozen=Trueによりフィールドの変更ができない
        try:
            models._models = []  # type: ignore
            assert False, "フィールドの変更が可能になっています"
        except AttributeError:
            # 変更できないことが期待される動作
            pass

    def test_merge_新しいインスタンスが返されること(self):
        # Given: Models
        models1 = Models([ModelDefinition("User", "program", [], [])])
        models2 = Models([ModelDefinition("Product", "datastore", [], [])])

        # When: mergeを呼ぶ
        result = Models.merge([models1, models2])

        # Then: 新しいModelsインスタンスが返される
        assert result is not models1
        assert result is not models2

    def test_with_dynamic_fields_新しいインスタンスが返されること(self):
        # Given: ModelsとLineageEntries
        models = Models([ModelDefinition("Target", "program", [], [])])
        lineage = LineageEntries([
            LineageEntry(["source"], "Target.field", None)
        ])

        # When: with_dynamic_fieldsを呼ぶ
        result = models.with_dynamic_fields(lineage)

        # Then: 新しいModelsインスタンスが返される
        assert result is not models
