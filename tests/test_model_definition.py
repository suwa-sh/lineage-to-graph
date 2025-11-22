"""
ModelDefinitionクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import ModelDefinition


class TestModelDefinition:
    """ModelDefinitionクラスのテスト"""

    def test_to_dict_childrenがある場合_childrenが含まれること(self):
        # Given: children を持つModelDefinition
        child = ModelDefinition(
            name="Child",
            type="program",
            props=["childField"],
            children=[]
        )
        model = ModelDefinition(
            name="Parent",
            type="program",
            props=["parentField"],
            children=[child]
        )

        # When: to_dictを呼ぶ
        result = model.to_dict()

        # Then: childrenがdict形式で含まれる
        # 注：空のchildrenは含まれない
        assert result == {
            "name": "Parent",
            "type": "program",
            "props": ["parentField"],
            "children": [
                {
                    "name": "Child",
                    "type": "program",
                    "props": ["childField"]
                }
            ]
        }

    def test_to_dict_childrenがない場合_childrenキーが含まれないこと(self):
        # Given: childrenを持たないModelDefinition
        model = ModelDefinition(
            name="SimpleModel",
            type="datastore",
            props=["field1", "field2"],
            children=[]
        )

        # When: to_dictを呼ぶ
        result = model.to_dict()

        # Then: childrenキーが含まれない
        assert result == {
            "name": "SimpleModel",
            "type": "datastore",
            "props": ["field1", "field2"]
        }
        assert "children" not in result

    def test_to_dict_propsが空の場合_空のリストが含まれること(self):
        # Given: propsが空のModelDefinition
        model = ModelDefinition(
            name="EmptyProps",
            type="program",
            props=[],
            children=[]
        )

        # When: to_dictを呼ぶ
        result = model.to_dict()

        # Then: propsは空のリストとして含まれる
        assert result == {
            "name": "EmptyProps",
            "type": "program",
            "props": []
        }

    def test_from_dict_完全なデータの場合_正しくModelDefinitionが生成されること(self):
        # Given: 完全なデータ辞書
        data = {
            "name": "User",
            "type": "program",
            "props": ["id", "name", "email"],
            "children": [
                {
                    "name": "Address",
                    "type": "program",
                    "props": ["zipCode", "city"]
                }
            ]
        }

        # When: from_dictを呼ぶ
        result = ModelDefinition.from_dict(data)

        # Then: 正しくModelDefinitionが生成される
        assert result.name == "User"
        assert result.type == "program"
        assert result.props == ["id", "name", "email"]
        assert len(result.children) == 1
        assert result.children[0].name == "Address"

    def test_from_dict_childrenがない場合_空のリストとして扱われること(self):
        # Given: childrenを含まないデータ辞書
        data = {
            "name": "Product",
            "type": "datastore",
            "props": ["id", "name"]
        }

        # When: from_dictを呼ぶ
        result = ModelDefinition.from_dict(data)

        # Then: childrenは空のリストになる
        assert result.name == "Product"
        assert result.type == "datastore"
        assert result.props == ["id", "name"]
        assert result.children == []

    def test_from_dict_propsが空の場合_空のリストとして扱われること(self):
        # Given: propsが空のデータ辞書
        data = {
            "name": "Empty",
            "type": "program",
            "props": []
        }

        # When: from_dictを呼ぶ
        result = ModelDefinition.from_dict(data)

        # Then: propsは空のリスト
        assert result.props == []

    def test_to_dict_from_dict_ラウンドトリップが正しく動作すること(self):
        # Given: ModelDefinition
        original = ModelDefinition(
            name="Test",
            type="program",
            props=["field1"],
            children=[
                ModelDefinition(
                    name="Nested",
                    type="datastore",
                    props=["nestedField"],
                    children=[]
                )
            ]
        )

        # When: to_dict -> from_dict でラウンドトリップ
        dict_data = original.to_dict()
        restored = ModelDefinition.from_dict(dict_data)

        # Then: 元のデータと一致する
        assert restored.name == original.name
        assert restored.type == original.type
        assert restored.props == original.props
        assert len(restored.children) == len(original.children)
        assert restored.children[0].name == original.children[0].name
