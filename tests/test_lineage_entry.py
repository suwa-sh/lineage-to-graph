"""
LineageEntryクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import LineageEntry


class TestLineageEntry:
    """LineageEntryクラスのテスト"""

    def test_to_dict_transformがある場合_transformが含まれること(self):
        # Given: transformを持つLineageEntry
        entry = LineageEntry(
            from_refs=["Source.field"],
            to_ref="Target.field",
            transform="upper()"
        )

        # When: to_dictを呼ぶ
        result = entry.to_dict()

        # Then: transformが含まれる
        assert result == {
            "from": ["Source.field"],
            "to": "Target.field",
            "transform": "upper()"
        }

    def test_to_dict_transformがない場合_transformキーが含まれないこと(self):
        # Given: transformを持たないLineageEntry
        entry = LineageEntry(
            from_refs=["Source.field"],
            to_ref="Target.field",
            transform=None
        )

        # When: to_dictを呼ぶ
        result = entry.to_dict()

        # Then: transformキーが含まれない
        assert result == {
            "from": ["Source.field"],
            "to": "Target.field"
        }
        assert "transform" not in result

    def test_to_dict_複数のfrom_refsの場合_リストとして返されること(self):
        # Given: 複数のfrom_refsを持つLineageEntry
        entry = LineageEntry(
            from_refs=["Source1.field", "Source2.field", "literal_value"],
            to_ref="Target.field",
            transform="concat"
        )

        # When: to_dictを呼ぶ
        result = entry.to_dict()

        # Then: from_refsがリストとして含まれる
        assert result["from"] == ["Source1.field", "Source2.field", "literal_value"]

    def test_from_dict_fromが文字列の場合_リストに変換されること(self):
        # Given: fromが文字列のデータ辞書
        data = {
            "from": "Source.field",
            "to": "Target.field"
        }

        # When: from_dictを呼ぶ
        result = LineageEntry.from_dict(data)

        # Then: from_refsがリストに変換される
        assert result.from_refs == ["Source.field"]
        assert result.to_ref == "Target.field"
        assert result.transform is None

    def test_from_dict_fromがリストの場合_そのまま使用されること(self):
        # Given: fromがリストのデータ辞書
        data = {
            "from": ["Source1.field", "Source2.field"],
            "to": "Target.field",
            "transform": "merge"
        }

        # When: from_dictを呼ぶ
        result = LineageEntry.from_dict(data)

        # Then: from_refsがそのまま使用される
        assert result.from_refs == ["Source1.field", "Source2.field"]
        assert result.to_ref == "Target.field"
        assert result.transform == "merge"

    def test_from_dict_transformがない場合_Noneになること(self):
        # Given: transformを含まないデータ辞書
        data = {
            "from": ["Source.field"],
            "to": "Target.field"
        }

        # When: from_dictを呼ぶ
        result = LineageEntry.from_dict(data)

        # Then: transformはNone
        assert result.transform is None

    def test_to_dict_from_dict_ラウンドトリップが正しく動作すること(self):
        # Given: LineageEntry
        original = LineageEntry(
            from_refs=["Source.field"],
            to_ref="Target.field",
            transform="normalize"
        )

        # When: to_dict -> from_dict でラウンドトリップ
        dict_data = original.to_dict()
        restored = LineageEntry.from_dict(dict_data)

        # Then: 元のデータと一致する
        assert restored.from_refs == original.from_refs
        assert restored.to_ref == original.to_ref
        assert restored.transform == original.transform

    def test_from_dict_fromが空のリストの場合_空のリストになること(self):
        # Given: fromが空リストのデータ辞書
        data = {
            "from": [],
            "to": "Target.field"
        }

        # When: from_dictを呼ぶ
        result = LineageEntry.from_dict(data)

        # Then: from_refsは空のリスト
        assert result.from_refs == []
        assert result.to_ref == "Target.field"
