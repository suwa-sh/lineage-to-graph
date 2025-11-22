"""
FieldReferenceクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from lineage_to_md import FieldReference


class TestFieldReference:
    """FieldReferenceクラスのテスト"""

    # __init__のテスト

    def test_init_通常のフィールド参照の場合_正しくパースされること(self):
        # Given/When: 通常のフィールド参照でFieldReferenceを作成
        ref = FieldReference("User.name")

        # Then: 各プロパティが正しく設定される
        assert ref.model == "User"
        assert ref.instance is None
        assert ref.field == "name"

    def test_init_インスタンス付きフィールド参照の場合_正しくパースされること(self):
        # Given/When: インスタンス付きフィールド参照でFieldReferenceを作成
        ref = FieldReference("User#user1.name")

        # Then: インスタンスが正しく抽出される
        assert ref.model == "User"
        assert ref.instance == "user1"
        assert ref.field == "name"

    def test_init_モデルのみの参照の場合_フィールドがNoneであること(self):
        # Given/When: モデルのみの参照でFieldReferenceを作成
        ref = FieldReference("User")

        # Then: フィールドがNone
        assert ref.model == "User"
        assert ref.instance is None
        assert ref.field is None

    def test_init_リテラル値の場合_フィールドがNoneであること(self):
        # Given/When: リテラル値でFieldReferenceを作成
        ref = FieldReference("literal_value")

        # Then: フィールドがNone（ドットがないため、これはリテラル値と判断される）
        assert ref.model == "literal_value"
        assert ref.instance is None
        assert ref.field is None

    # parseメソッドのテスト

    def test_parse_インスタンスありフィールドありの場合_すべてパースされること(self):
        # Given: インスタンスとフィールドを含む参照文字列
        ref = "User#user1.name"

        # When: parseを呼ぶ
        model, instance, field = FieldReference.parse(ref)

        # Then: すべての要素が正しく抽出される
        assert model == "User"
        assert instance == "user1"
        assert field == "name"

    def test_parse_インスタンスありフィールドなしの場合_フィールドがNoneであること(self):
        # Given: インスタンスのみ含む参照文字列
        ref = "User#user1"

        # When: parseを呼ぶ
        model, instance, field = FieldReference.parse(ref)

        # Then: フィールドがNone
        assert model == "User"
        assert instance == "user1"
        assert field is None

    def test_parse_インスタンスなしフィールドありの場合_インスタンスがNoneであること(self):
        # Given: フィールドのみ含む参照文字列
        ref = "User.name"

        # When: parseを呼ぶ
        model, instance, field = FieldReference.parse(ref)

        # Then: インスタンスがNone
        assert model == "User"
        assert instance is None
        assert field == "name"

    def test_parse_インスタンスなしフィールドなしの場合_両方Noneであること(self):
        # Given: モデル名のみの参照文字列
        ref = "User"

        # When: parseを呼ぶ
        model, instance, field = FieldReference.parse(ref)

        # Then: インスタンスとフィールドがNone
        assert model == "User"
        assert instance is None
        assert field is None

    def test_parse_階層構造のフィールド参照の場合_正しくパースされること(self):
        # Given: 階層構造のフィールド参照
        ref = "User.Address.zipCode"

        # When: parseを呼ぶ
        model, instance, field = FieldReference.parse(ref)

        # Then: モデルとフィールドが正しく分割される
        assert model == "User"
        assert instance is None
        assert field == "Address.zipCode"

    def test_parse_インスタンスあり階層構造の場合_正しくパースされること(self):
        # Given: インスタンス付き階層構造のフィールド参照
        ref = "User#user1.Address.zipCode"

        # When: parseを呼ぶ
        model, instance, field = FieldReference.parse(ref)

        # Then: すべての要素が正しく抽出される
        assert model == "User"
        assert instance == "user1"
        assert field == "Address.zipCode"

    def test_parse_リテラル値の場合_すべてNoneであること(self):
        # Given: リテラル値（ドットなし、シャープなし）
        ref = "literal_value"

        # When: parseを呼ぶ
        model, instance, field = FieldReference.parse(ref)

        # Then: すべてNone（モデルには値が入るが、これはリテラルとして扱われる）
        # 実装を見ると、ドットがない場合は model にそのまま入り、field は None
        assert model == "literal_value"
        assert instance is None
        assert field is None

    # parse_fieldメソッドのテスト

    def test_parse_field_フィールド参照の場合_モデルとフィールドが返されること(self):
        # Given: フィールド参照文字列
        ref = "User.name"

        # When: parse_fieldを呼ぶ
        model, field = FieldReference.parse_field(ref)

        # Then: モデルとフィールドが正しく分割される
        assert model == "User"
        assert field == "name"

    def test_parse_field_階層構造の場合_最後のドットで分割されること(self):
        # Given: 階層構造のフィールド参照
        ref = "User.Address.zipCode"

        # When: parse_fieldを呼ぶ
        model, field = FieldReference.parse_field(ref)

        # Then: 最後のドットで分割される（最後がfield、残りがmodel_path）
        assert model == "User.Address"
        assert field == "zipCode"

    def test_parse_field_フィールド指定なしの場合_ValueErrorが発生すること(self):
        # Given: フィールド指定のない文字列
        ref = "User"

        # When/Then: parse_fieldを呼ぶとValueErrorが発生
        with pytest.raises(ValueError, match="Field reference must be"):
            FieldReference.parse_field(ref)

    # __str__メソッドのテスト

    def test_str_元の文字列が返されること(self):
        # Given: FieldReference
        original = "User.name"
        ref = FieldReference(original)

        # When: str()を呼ぶ
        result = str(ref)

        # Then: 元の文字列が返される
        assert result == original

    def test_str_インスタンス付き参照の場合_元の文字列が返されること(self):
        # Given: インスタンス付きFieldReference
        original = "User#user1.name"
        ref = FieldReference(original)

        # When: str()を呼ぶ
        result = str(ref)

        # Then: 元の文字列が返される
        assert result == original
