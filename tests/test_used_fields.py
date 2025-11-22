"""
UsedFieldsクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import UsedFields


class TestUsedFields:
    """UsedFieldsクラスのテスト"""

    def test_get_fields_フィールドが存在する場合_フィールドセットが返されること(self):
        # Given: フィールドを持つUsedFields
        fields_dict = {
            "User": {"id", "name", "email"},
            "Product": {"id", "name"}
        }
        used_fields = UsedFields(fields_dict)

        # When: 存在するモデルパスのフィールドを取得
        result = used_fields.get_fields("User")

        # Then: フィールドセットが返される
        assert result == {"id", "name", "email"}

    def test_get_fields_フィールドが存在しない場合_空のセットが返されること(self):
        # Given: フィールドを持つUsedFields
        fields_dict = {"User": {"id", "name"}}
        used_fields = UsedFields(fields_dict)

        # When: 存在しないモデルパスのフィールドを取得
        result = used_fields.get_fields("Product")

        # Then: 空のセットが返される
        assert result == set()

    def test_get_fields_防御的コピーが返されること(self):
        # Given: フィールドを持つUsedFields
        fields_dict = {"User": {"id", "name"}}
        used_fields = UsedFields(fields_dict)

        # When: フィールドを取得
        result1 = used_fields.get_fields("User")
        result2 = used_fields.get_fields("User")

        # Then: 各呼び出しで別のオブジェクトが返される
        assert result1 == result2
        assert result1 is not result2

    def test_contains_モデルパスが存在する場合_Trueであること(self):
        # Given: フィールドを持つUsedFields
        fields_dict = {
            "User": {"id"},
            "Product": {"name"}
        }
        used_fields = UsedFields(fields_dict)

        # When: 存在するモデルパスでcontainsを呼ぶ
        result = used_fields.contains("User")

        # Then: Trueが返される
        assert result is True

    def test_contains_モデルパスが存在しない場合_Falseであること(self):
        # Given: フィールドを持つUsedFields
        fields_dict = {"User": {"id"}}
        used_fields = UsedFields(fields_dict)

        # When: 存在しないモデルパスでcontainsを呼ぶ
        result = used_fields.contains("Product")

        # Then: Falseが返される
        assert result is False

    def test_to_dict_すべてのフィールドが返されること(self):
        # Given: 複数のモデルとフィールドを持つUsedFields
        fields_dict = {
            "User": {"id", "name", "email"},
            "Product": {"id", "name"},
            "Order": set()
        }
        used_fields = UsedFields(fields_dict)

        # When: to_dictを呼ぶ
        result = used_fields.to_dict()

        # Then: すべてのモデルとフィールドが含まれる
        assert result == fields_dict

    def test_to_dict_防御的コピーが返されること(self):
        # Given: フィールドを持つUsedFields
        fields_dict = {
            "User": {"id", "name"},
            "Product": {"price"}
        }
        used_fields = UsedFields(fields_dict)

        # When: to_dictを呼ぶ
        result = used_fields.to_dict()

        # Then: 辞書とSet両方がコピーされている
        # 辞書レベルの比較
        assert result == fields_dict
        assert result is not fields_dict

        # Setレベルの比較
        assert result["User"] == fields_dict["User"]
        assert result["User"] is not fields_dict["User"]

    def test_to_dict_空の場合_空の辞書が返されること(self):
        # Given: 空のUsedFields
        used_fields = UsedFields({})

        # When: to_dictを呼ぶ
        result = used_fields.to_dict()

        # Then: 空の辞書が返される
        assert result == {}

    def test_immutable_frozenであること(self):
        # Given: UsedFields
        used_fields = UsedFields({"User": {"id"}})

        # When/Then: frozen=Trueによりフィールドの変更ができない
        try:
            used_fields._fields = {}  # type: ignore
            assert False, "フィールドの変更が可能になっています"
        except AttributeError:
            # 変更できないことが期待される動作
            pass
