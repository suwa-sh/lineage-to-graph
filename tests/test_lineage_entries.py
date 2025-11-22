"""
LineageEntriesクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import LineageEntries, LineageEntry, Models, ModelDefinition


class TestLineageEntries:
    """LineageEntriesクラスのテスト"""

    # to_listメソッドのテスト

    def test_to_list_すべてのエントリが返されること(self):
        # Given: 複数のLineageEntryを持つLineageEntries
        entries = [
            LineageEntry(["Source1.field"], "Target1.field", None),
            LineageEntry(["Source2.field"], "Target2.field", "transform")
        ]
        lineage = LineageEntries(entries)

        # When: to_listを呼ぶ
        result = lineage.to_list()

        # Then: すべてのエントリが返される
        assert len(result) == 2
        assert result[0].to_ref == "Target1.field"
        assert result[1].to_ref == "Target2.field"

    def test_to_list_防御的コピーが返されること(self):
        # Given: LineageEntries
        entries = [LineageEntry(["Source.field"], "Target.field", None)]
        lineage = LineageEntries(entries)

        # When: to_listを呼ぶ
        result = lineage.to_list()

        # Then: リストのコピーが返される
        assert result == entries
        assert result is not entries

    def test_to_list_空の場合_空のリストが返されること(self):
        # Given: 空のLineageEntries
        lineage = LineageEntries([])

        # When: to_listを呼ぶ
        result = lineage.to_list()

        # Then: 空のリストが返される
        assert result == []

    # __iter__メソッドのテスト

    def test_iter_すべてのエントリをイテレートできること(self):
        # Given: 複数のLineageEntryを持つLineageEntries
        entries = [
            LineageEntry(["S1.f1"], "T1.f1", None),
            LineageEntry(["S2.f2"], "T2.f2", None),
            LineageEntry(["S3.f3"], "T3.f3", None)
        ]
        lineage = LineageEntries(entries)

        # When: forループでイテレート
        result = list(lineage)

        # Then: すべてのエントリが取得できる
        assert len(result) == 3
        assert result == entries

    # from_dictsメソッドのテスト

    def test_from_dicts_辞書リストからLineageEntriesが生成されること(self):
        # Given: 辞書のリスト
        data = [
            {"from": "Source1.field", "to": "Target1.field"},
            {"from": ["S2.f1", "S2.f2"], "to": "Target2.field", "transform": "merge"}
        ]

        # When: from_dictsを呼ぶ
        result = LineageEntries.from_dicts(data)

        # Then: LineageEntriesが正しく生成される
        entries = result.to_list()
        assert len(entries) == 2
        assert entries[0].to_ref == "Target1.field"
        assert entries[1].transform == "merge"

    def test_from_dicts_空のリストの場合_空のLineageEntriesが生成されること(self):
        # Given: 空のリスト
        data = []

        # When: from_dictsを呼ぶ
        result = LineageEntries.from_dicts(data)

        # Then: 空のLineageEntriesが生成される
        assert result.to_list() == []

    # extract_referenced_fieldsメソッドのテスト

    def test_extract_referenced_fields_フィールド参照の場合_フィールドが抽出されること(self):
        # Given: フィールド参照を含むLineageEntries
        lineage = LineageEntries([
            LineageEntry(["User.id"], "Target.id", None),
            LineageEntry(["User.name"], "Target.name", None)
        ])
        models = Models([
            ModelDefinition("User", "program", ["id", "name"], [])
        ])

        # When: extract_referenced_fieldsを呼ぶ
        result = lineage.extract_referenced_fields(models)

        # Then: 参照されたフィールドが抽出される
        assert result.get_fields("User") == {"id", "name"}

    def test_extract_referenced_fields_モデル参照の場合_ワイルドカードが設定されること(self):
        # Given: モデル参照を含むLineageEntries
        lineage = LineageEntries([
            LineageEntry(["User"], "Target.data", None)
        ])
        models = Models([
            ModelDefinition("User", "program", ["id", "name"], [])
        ])

        # When: extract_referenced_fieldsを呼ぶ
        result = lineage.extract_referenced_fields(models)

        # Then: ワイルドカード('*')が設定される
        assert result.get_fields("User") == {"*"}

    def test_extract_referenced_fields_インスタンス参照の場合_フィールドが抽出されること(self):
        # Given: インスタンス参照を含むLineageEntries
        lineage = LineageEntries([
            LineageEntry(["User#user1.id"], "Target.id", None),
            LineageEntry(["User#user2.name"], "Target.name", None)
        ])
        models = Models([
            ModelDefinition("User", "program", ["id", "name"], [])
        ])

        # When: extract_referenced_fieldsを呼ぶ
        result = lineage.extract_referenced_fields(models)

        # Then: 参照されたフィールドがインスタンスごとに抽出される
        assert result.get_fields("User#user1") == {"id"}
        assert result.get_fields("User#user2") == {"name"}

    def test_extract_referenced_fields_階層構造の場合_正しいパスで抽出されること(self):
        # Given: 階層構造のフィールド参照を含むLineageEntries
        lineage = LineageEntries([
            LineageEntry(["Parent.Child.field"], "Target.field", None)
        ])
        models = Models([
            ModelDefinition("Parent", "program", [], [
                ModelDefinition("Child", "program", ["field"], [])
            ])
        ])

        # When: extract_referenced_fieldsを呼ぶ
        result = lineage.extract_referenced_fields(models)

        # Then: Parentモデルで、Child.field がフィールドとして抽出される
        # FieldReference.parse()は最初のドットで分割するため
        assert result.get_fields("Parent") == {"Child.field"}

    def test_extract_referenced_fields_toフィールドも抽出されること(self):
        # Given: from と to 両方にフィールド参照を含むLineageEntries
        lineage = LineageEntries([
            LineageEntry(["Source.input"], "Target.output", None)
        ])
        models = Models([
            ModelDefinition("Source", "program", ["input"], []),
            ModelDefinition("Target", "datastore", ["output"], [])
        ])

        # When: extract_referenced_fieldsを呼ぶ
        result = lineage.extract_referenced_fields(models)

        # Then: from と to 両方のフィールドが抽出される
        assert result.get_fields("Source") == {"input"}
        assert result.get_fields("Target") == {"output"}

    def test_extract_referenced_fields_複数fromの場合_すべて抽出されること(self):
        # Given: 複数のfromを持つLineageEntries
        lineage = LineageEntries([
            LineageEntry(["S1.f1", "S2.f2", "S3.f3"], "Target.result", None)
        ])
        models = Models([
            ModelDefinition("S1", "program", ["f1"], []),
            ModelDefinition("S2", "program", ["f2"], []),
            ModelDefinition("S3", "program", ["f3"], []),
            ModelDefinition("Target", "datastore", ["result"], [])
        ])

        # When: extract_referenced_fieldsを呼ぶ
        result = lineage.extract_referenced_fields(models)

        # Then: すべてのfromフィールドが抽出される
        assert result.get_fields("S1") == {"f1"}
        assert result.get_fields("S2") == {"f2"}
        assert result.get_fields("S3") == {"f3"}

    def test_extract_referenced_fields_リテラル値の場合_無視されること(self):
        # Given: リテラル値を含むLineageEntries
        lineage = LineageEntries([
            LineageEntry(["literal_value"], "Target.field", None)
        ])
        models = Models([
            ModelDefinition("Target", "datastore", ["field"], [])
        ])

        # When: extract_referenced_fieldsを呼ぶ
        result = lineage.extract_referenced_fields(models)

        # Then: リテラルは無視され、toのみ抽出される
        assert result.contains("Target")
        assert not result.contains("literal_value")

    def test_extract_referenced_fields_ワイルドカード設定後のフィールド追加は無視されること(self):
        # Given: モデル参照後にフィールド参照があるLineageEntries
        lineage = LineageEntries([
            LineageEntry(["User"], "Target.data", None),  # ワイルドカード設定
            LineageEntry(["User.name"], "Target.name", None)  # これは無視される
        ])
        models = Models([
            ModelDefinition("User", "program", ["id", "name"], [])
        ])

        # When: extract_referenced_fieldsを呼ぶ
        result = lineage.extract_referenced_fields(models)

        # Then: ワイルドカードのみ（個別フィールドは追加されない）
        assert result.get_fields("User") == {"*"}

    def test_immutable_frozenであること(self):
        # Given: LineageEntries
        lineage = LineageEntries([LineageEntry(["S.f"], "T.f", None)])

        # When/Then: frozen=Trueによりフィールドの変更ができない
        try:
            lineage._entries = []  # type: ignore
            assert False, "フィールドの変更が可能になっています"
        except AttributeError:
            # 変更できないことが期待される動作
            pass
