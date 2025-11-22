"""
ModelInstancesクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import ModelInstances


class TestModelInstances:
    """ModelInstancesクラスのテスト"""

    def test_get_instances_インスタンスが存在する場合_インスタンスセットが返されること(self):
        # Given: インスタンスを持つModelInstances
        instances_dict = {
            "User": {"user1", "user2"},
            "Product": {"product1"}
        }
        instances = ModelInstances(instances_dict)

        # When: 存在するモデルのインスタンスを取得
        result = instances.get_instances("User")

        # Then: インスタンスセットが返される
        assert result == {"user1", "user2"}

    def test_get_instances_インスタンスが存在しない場合_空のセットが返されること(self):
        # Given: インスタンスを持つModelInstances
        instances_dict = {"User": {"user1"}}
        instances = ModelInstances(instances_dict)

        # When: 存在しないモデルのインスタンスを取得
        result = instances.get_instances("Product")

        # Then: 空のセットが返される
        assert result == set()

    def test_get_instances_防御的コピーが返されること(self):
        # Given: インスタンスを持つModelInstances
        instances_dict = {"User": {"user1", "user2"}}
        instances = ModelInstances(instances_dict)

        # When: インスタンスを取得
        result1 = instances.get_instances("User")
        result2 = instances.get_instances("User")

        # Then: 各呼び出しで別のオブジェクトが返される
        assert result1 == result2
        assert result1 is not result2

    def test_get_instances_空のインスタンスセットの場合_空のセットが返されること(self):
        # Given: 空のインスタンスセットを持つModelInstances
        instances_dict = {"User": set()}
        instances = ModelInstances(instances_dict)

        # When: インスタンスを取得
        result = instances.get_instances("User")

        # Then: 空のセットが返される
        assert result == set()

    def test_to_dict_すべてのインスタンスが返されること(self):
        # Given: 複数のモデルとインスタンスを持つModelInstances
        instances_dict = {
            "User": {"user1", "user2"},
            "Product": {"product1"},
            "Order": set()
        }
        instances = ModelInstances(instances_dict)

        # When: to_dictを呼ぶ
        result = instances.to_dict()

        # Then: すべてのモデルとインスタンスが含まれる
        assert result == instances_dict

    def test_to_dict_防御的コピーが返されること(self):
        # Given: インスタンスを持つModelInstances
        instances_dict = {
            "User": {"user1", "user2"},
            "Product": {"product1"}
        }
        instances = ModelInstances(instances_dict)

        # When: to_dictを呼ぶ
        result = instances.to_dict()

        # Then: 辞書とSet両方がコピーされている
        # 辞書レベルの比較
        assert result == instances_dict
        assert result is not instances_dict

        # Setレベルの比較
        assert result["User"] == instances_dict["User"]
        assert result["User"] is not instances_dict["User"]

    def test_to_dict_空の場合_空の辞書が返されること(self):
        # Given: 空のModelInstances
        instances = ModelInstances({})

        # When: to_dictを呼ぶ
        result = instances.to_dict()

        # Then: 空の辞書が返される
        assert result == {}

    def test_immutable_frozenであること(self):
        # Given: ModelInstances
        instances = ModelInstances({"User": {"user1"}})

        # When/Then: frozen=Trueによりフィールドの変更ができない
        try:
            instances._instances = {}  # type: ignore
            assert False, "フィールドの変更が可能になっています"
        except AttributeError:
            # 変更できないことが期待される動作
            pass
