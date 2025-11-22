"""
ModelParserクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import (
    ModelParser, Models, ModelDefinition, UsedFields, ModelInstances,
    ParsedModelsData
)


class TestModelParser:
    """ModelParserクラスのテスト"""

    # parseメソッドのテスト

    def test_parse_parsed_dataがNoneの場合_新しいParsedModelsDataが作成されること(self):
        # Given: ModelParserとparsed_data=None
        models = Models([
            ModelDefinition("User", "program", ("id",), ())
        ])
        parser = ModelParser(models)

        # When: parseを呼ぶ
        result = parser.parse(parsed_data=None)

        # Then: 新しいParsedModelsDataが作成される
        assert isinstance(result, ParsedModelsData)
        assert "User" in result.model_types
        assert result.model_types["User"] == "program"

    def test_parse_parsed_dataが指定された場合_既存データに追加されること(self):
        # Given: ModelParserと既存のParsedModelsData
        models = Models([
            ModelDefinition("User", "program", ("id",), ())
        ])
        parser = ModelParser(models)
        existing_data = ParsedModelsData(
            model_types={"ExistingModel": "datastore"},
            field_nodes_by_model={},
            field_node_ids={},
            model_hierarchy={}
        )

        # When: 既存データを指定してparseを呼ぶ
        result = parser.parse(parsed_data=existing_data)

        # Then: 既存データに追加される
        assert "ExistingModel" in result.model_types  # 既存
        assert "User" in result.model_types  # 新規

    def test_parse_複数モデルの場合_すべて解析されること(self):
        # Given: 複数のモデルを持つModels
        models = Models([
            ModelDefinition("User", "program", ("id",), ()),
            ModelDefinition("Product", "datastore", ("name",), ())
        ])
        parser = ModelParser(models)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: すべてのモデルが解析される
        assert "User" in result.model_types
        assert "Product" in result.model_types

    # _parse_modelメソッドのテスト（間接的にparseから）

    def test_parse_parent_prefixなしの場合_ルートパスが使用されること(self):
        # Given: ModelParserとparent_prefix=""
        models = Models([
            ModelDefinition("RootModel", "program", ("field",), ())
        ])
        parser = ModelParser(models)

        # When: parent_prefix=""でparseを呼ぶ
        result = parser.parse(parent_prefix="")

        # Then: ルートパスが使用される
        assert "RootModel" in result.model_types
        assert "RootModel.field" in result.field_node_ids

    def test_parse_parent_prefixありの場合_ネストされたパスが使用されること(self):
        # Given: ModelParserとparent_prefix="Parent"
        models = Models([
            ModelDefinition("Child", "program", ("field",), ())
        ])
        parser = ModelParser(models)

        # When: parent_prefix="Parent"でparseを呼ぶ
        result = parser.parse(parent_prefix="Parent")

        # Then: ネストされたパスが使用される
        assert "Parent.Child" in result.model_types
        assert "Parent.Child.field" in result.field_node_ids

    def test_parse_インスタンスなしの場合_デフォルトインスタンスが使用されること(self):
        # Given: ModelParserとmodel_instances=None
        models = Models([
            ModelDefinition("Model", "program", ("field",), ())
        ])
        parser = ModelParser(models, model_instances=None)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: デフォルトインスタンス（インスタンスなし）で処理される
        assert "Model" in result.model_types
        assert "Model" in result.field_nodes_by_model

    def test_parse_インスタンスありの場合_各インスタンスが処理されること(self):
        # Given: ModelParserとModelInstances
        models = Models([
            ModelDefinition("Money", "program", ("amount",), ())
        ])
        model_instances = ModelInstances({"Money": {"jpy", "usd"}})
        parser = ModelParser(models, model_instances=model_instances)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: 各インスタンスが処理される
        assert "Money#jpy" in result.model_types
        assert "Money#usd" in result.model_types
        assert "Money#jpy" in result.field_nodes_by_model
        assert "Money#usd" in result.field_nodes_by_model

    def test_parse_子モデルがある場合_再帰的に解析されること(self):
        # Given: 子モデルを持つModels
        models = Models([
            ModelDefinition(
                "Parent",
                "program",
                ("p_field",),
                (ModelDefinition("Child", "program", ("c_field",), ()),)
            )
        ])
        parser = ModelParser(models)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: 親子両方が解析される
        assert "Parent" in result.model_types
        assert "Parent.Child" in result.model_types
        assert "Parent" in result.model_hierarchy
        assert result.model_hierarchy["Parent"]["children"] == ["Parent.Child"]

    # _process_model_instanceメソッドのテスト（間接的にparseから）

    def test_parse_インスタンス付きの場合_インスタンスパスが生成されること(self):
        # Given: インスタンス付きモデル
        models = Models([
            ModelDefinition("Money", "program", ("amount",), ())
        ])
        model_instances = ModelInstances({"Money": {"jpy"}})
        parser = ModelParser(models, model_instances=model_instances)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: インスタンスパスが生成される
        assert "Money#jpy" in result.model_types
        assert "Money#jpy.amount" in result.field_node_ids

    def test_parse_インスタンスなしの場合_モデルパスが使用されること(self):
        # Given: インスタンスなしモデル
        models = Models([
            ModelDefinition("User", "program", ("id",), ())
        ])
        parser = ModelParser(models, model_instances=None)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: モデルパスが使用される（#なし）
        assert "User" in result.model_types
        assert "User.id" in result.field_node_ids

    def test_parse_model_typesに登録されること(self):
        # Given: ModelParser
        models = Models([
            ModelDefinition("TestModel", "datastore", (), ())
        ])
        parser = ModelParser(models)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: model_typesに登録される
        assert "TestModel" in result.model_types
        assert result.model_types["TestModel"] == "datastore"

    def test_parse_model_hierarchyに登録されること(self):
        # Given: 親子モデル
        models = Models([
            ModelDefinition(
                "Parent",
                "program",
                (),
                (ModelDefinition("Child", "program", (), ()),)
            )
        ])
        parser = ModelParser(models)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: model_hierarchyに登録される
        assert "Parent" in result.model_hierarchy
        assert result.model_hierarchy["Parent"]["parent"] is None
        assert result.model_hierarchy["Parent"]["children"] == ["Parent.Child"]
        assert result.model_hierarchy["Parent"]["instance"] is None

    def test_parse_field_nodes_by_modelに登録されること(self):
        # Given: フィールドを持つモデル
        models = Models([
            ModelDefinition("User", "program", ("id", "name"), ())
        ])
        parser = ModelParser(models)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: field_nodes_by_modelに登録される
        assert "User" in result.field_nodes_by_model
        nodes = result.field_nodes_by_model["User"]
        field_names = [label for _, label in nodes]
        assert "id" in field_names
        assert "name" in field_names

    # _should_filter_fieldsメソッドのテスト（間接的にparseから）

    def test_parse_used_fieldsがNoneの場合_全フィールドが含まれること(self):
        # Given: used_fields=None
        models = Models([
            ModelDefinition("Model", "program", ("field1", "field2"), ())
        ])
        parser = ModelParser(models, used_fields=None)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: すべてのフィールドが含まれる
        nodes = result.field_nodes_by_model["Model"]
        field_names = [label for _, label in nodes]
        assert "field1" in field_names
        assert "field2" in field_names

    def test_parse_csv_model_namesが空の場合_全フィールドが含まれること(self):
        # Given: csv_model_names=空
        models = Models([
            ModelDefinition("Model", "program", ("field1", "field2"), ())
        ])
        used_fields = UsedFields({"Model": {"field1"}})
        parser = ModelParser(models, used_fields=used_fields, csv_model_names=set())

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: フィルタリングされず全フィールドが含まれる
        nodes = result.field_nodes_by_model["Model"]
        field_names = [label for _, label in nodes]
        assert "field1" in field_names
        assert "field2" in field_names

    def test_parse_CSV由来でused_fieldsに含まれる場合_フィルタリングされること(self):
        # Given: CSV由来モデルとused_fields
        models = Models([
            ModelDefinition("CSVModel", "program", ("field1", "field2", "field3"), ())
        ])
        used_fields = UsedFields({"CSVModel": {"field1", "field3"}})
        csv_model_names = {"CSVModel"}
        parser = ModelParser(models, used_fields=used_fields, csv_model_names=csv_model_names)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: used_fieldsに含まれるフィールドのみが含まれる
        nodes = result.field_nodes_by_model["CSVModel"]
        field_names = [label for _, label in nodes]
        assert "field1" in field_names
        assert "field2" not in field_names  # フィルタリングされた
        assert "field3" in field_names

    def test_parse_CSV由来でない場合_フィルタリングされないこと(self):
        # Given: YAML定義モデル（CSV由来でない）
        models = Models([
            ModelDefinition("YAMLModel", "program", ("field1", "field2"), ())
        ])
        used_fields = UsedFields({"YAMLModel": {"field1"}})
        csv_model_names = {"OtherModel"}  # YAMLModelは含まれない
        parser = ModelParser(models, used_fields=used_fields, csv_model_names=csv_model_names)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: フィルタリングされず全フィールドが含まれる
        nodes = result.field_nodes_by_model["YAMLModel"]
        field_names = [label for _, label in nodes]
        assert "field1" in field_names
        assert "field2" in field_names

    # _parse_fieldsメソッドのテスト（間接的にparseから）

    def test_parse_通常のフィールドの場合_ノードリストが生成されること(self):
        # Given: フィールドを持つモデル
        models = Models([
            ModelDefinition("User", "program", ("id", "name"), ())
        ])
        parser = ModelParser(models)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: ノードリストが生成される
        nodes = result.field_nodes_by_model["User"]
        assert len(nodes) == 2
        assert nodes[0][1] == "id"
        assert nodes[1][1] == "name"

    def test_parse_インスタンスありの場合_インスタンス付きノードIDが生成されること(self):
        # Given: インスタンス付きモデル
        models = Models([
            ModelDefinition("Money", "program", ("amount",), ())
        ])
        model_instances = ModelInstances({"Money": {"jpy"}})
        parser = ModelParser(models, model_instances=model_instances)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: インスタンス付きノードIDが生成される
        nodes = result.field_nodes_by_model["Money#jpy"]
        node_id, field_name = nodes[0]
        assert field_name == "amount"
        assert "jpy" in node_id  # インスタンスIDがノードIDに含まれる

    def test_parse_field_node_idsに登録されること(self):
        # Given: フィールドを持つモデル
        models = Models([
            ModelDefinition("User", "program", ("id",), ())
        ])
        parser = ModelParser(models)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: field_node_idsに登録される
        assert "User.id" in result.field_node_ids
        assert result.field_node_ids["User.id"] == "User_id"

    # _is_field_usedメソッドのテスト（間接的にparseから）

    def test_parse_used_fieldsがNoneの場合_すべてのフィールドが使用されること(self):
        # Given: used_fields=None
        models = Models([
            ModelDefinition("Model", "program", ("field1", "field2"), ())
        ])
        parser = ModelParser(models, used_fields=None)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: すべてのフィールドが含まれる
        nodes = result.field_nodes_by_model["Model"]
        assert len(nodes) == 2

    def test_parse_アスタリスクの場合_すべてのフィールドが使用されること(self):
        # Given: used_fieldsに'*'を含む
        models = Models([
            ModelDefinition("CSVModel", "program", ("field1", "field2", "field3"), ())
        ])
        used_fields = UsedFields({"CSVModel": {"*"}})
        csv_model_names = {"CSVModel"}
        parser = ModelParser(models, used_fields=used_fields, csv_model_names=csv_model_names)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: すべてのフィールドが含まれる
        nodes = result.field_nodes_by_model["CSVModel"]
        assert len(nodes) == 3

    def test_parse_フィールドが含まれる場合_そのフィールドが使用されること(self):
        # Given: 特定フィールドのみused_fieldsに含む
        models = Models([
            ModelDefinition("CSVModel", "program", ("field1", "field2"), ())
        ])
        used_fields = UsedFields({"CSVModel": {"field1"}})
        csv_model_names = {"CSVModel"}
        parser = ModelParser(models, used_fields=used_fields, csv_model_names=csv_model_names)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: 含まれるフィールドのみが使用される
        nodes = result.field_nodes_by_model["CSVModel"]
        field_names = [label for _, label in nodes]
        assert "field1" in field_names
        assert "field2" not in field_names

    def test_parse_フィールドが含まれない場合_そのフィールドは除外されること(self):
        # Given: used_fieldsに含まれないフィールド
        models = Models([
            ModelDefinition("CSVModel", "program", ("used", "unused"), ())
        ])
        used_fields = UsedFields({"CSVModel": {"used"}})
        csv_model_names = {"CSVModel"}
        parser = ModelParser(models, used_fields=used_fields, csv_model_names=csv_model_names)

        # When: parseを呼ぶ
        result = parser.parse()

        # Then: 含まれないフィールドは除外される
        nodes = result.field_nodes_by_model["CSVModel"]
        field_names = [label for _, label in nodes]
        assert "used" in field_names
        assert "unused" not in field_names
