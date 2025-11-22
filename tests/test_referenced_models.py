"""
ReferencedModelsクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import ReferencedModels


class TestReferencedModels:
    """ReferencedModelsクラスのテスト"""

    def test_contains_名前が含まれる場合_Trueであること(self):
        # Given: モデル名が含まれるReferencedModels
        models = ReferencedModels({"Model1", "Model2", "Model3"})

        # When: 含まれる名前でcontainsを呼ぶ
        result = models.contains("Model2")

        # Then: Trueが返される
        assert result is True

    def test_contains_名前が含まれない場合_Falseであること(self):
        # Given: モデル名が含まれるReferencedModels
        models = ReferencedModels({"Model1", "Model2"})

        # When: 含まれない名前でcontainsを呼ぶ
        result = models.contains("Model3")

        # Then: Falseが返される
        assert result is False

    def test_contains_空の場合_Falseであること(self):
        # Given: 空のReferencedModels
        models = ReferencedModels(set())

        # When: 任意の名前でcontainsを呼ぶ
        result = models.contains("AnyModel")

        # Then: Falseが返される
        assert result is False

    def test_difference_差分がある場合_差分が返されること(self):
        # Given: 2つのReferencedModels
        models1 = ReferencedModels({"Model1", "Model2", "Model3"})
        models2 = ReferencedModels({"Model2", "Model4"})

        # When: differenceを呼ぶ
        result = models1.difference(models2)

        # Then: models1にだけ含まれる要素が返される
        assert result.to_set() == {"Model1", "Model3"}

    def test_difference_差分がない場合_空のReferencedModelsが返されること(self):
        # Given: 同じ内容の2つのReferencedModels
        models1 = ReferencedModels({"Model1", "Model2"})
        models2 = ReferencedModels({"Model1", "Model2"})

        # When: differenceを呼ぶ
        result = models1.difference(models2)

        # Then: 空のセットが返される
        assert result.to_set() == set()

    def test_difference_空との差分の場合_元のセットが返されること(self):
        # Given: ReferencedModelsと空のReferencedModels
        models1 = ReferencedModels({"Model1", "Model2"})
        models2 = ReferencedModels(set())

        # When: differenceを呼ぶ
        result = models1.difference(models2)

        # Then: 元のセットがそのまま返される
        assert result.to_set() == {"Model1", "Model2"}

    def test_to_set_防御的コピーが返されること(self):
        # Given: ReferencedModels
        original_set = {"Model1", "Model2"}
        models = ReferencedModels(original_set)

        # When: to_setを呼ぶ
        result = models.to_set()

        # Then: セットのコピーが返される（元のセットと別オブジェクト）
        assert result == original_set
        assert result is not original_set

    def test_iter_すべての要素をイテレートできること(self):
        # Given: 複数の要素を持つReferencedModels
        models = ReferencedModels({"Model1", "Model2", "Model3"})

        # When: forループでイテレート
        result = set(models)

        # Then: すべての要素が取得できる
        assert result == {"Model1", "Model2", "Model3"}

    def test_iter_空の場合_要素がないこと(self):
        # Given: 空のReferencedModels
        models = ReferencedModels(set())

        # When: forループでイテレート
        result = list(models)

        # Then: 要素がない
        assert result == []

    def test_immutable_frozenであること(self):
        # Given: ReferencedModels
        models = ReferencedModels({"Model1"})

        # When/Then: frozen=Trueによりフィールドの変更ができない
        try:
            models._names = {"Modified"}  # type: ignore
            assert False, "フィールドの変更が可能になっています"
        except AttributeError:
            # 変更できないことが期待される動作
            pass
