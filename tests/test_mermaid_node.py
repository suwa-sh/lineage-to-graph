"""
MermaidNodeクラスのunit test

複合条件カバレッジ: 100%
テストパターン: Given/When/Then方式
"""

import sys
from pathlib import Path

# lineage_to_md.pyをインポートできるようにパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_to_md import MermaidNode


class TestMermaidNode:
    """MermaidNodeクラスのテスト"""

    # to_mermaid_lineメソッドのテスト

    def test_to_mermaid_line_通常のノードの場合_正しいMermaid行が生成されること(self):
        # Given: MermaidNode
        node = MermaidNode(
            node_id="user_id",
            label="id",
            style_class="property"
        )

        # When: to_mermaid_lineを呼ぶ
        result = node.to_mermaid_line()

        # Then: 正しいMermaid行が返される
        assert result == 'user_id["id"]:::property'

    # sanitize_idメソッドのテスト

    def test_sanitize_id_通常の文字列の場合_そのまま返されること(self):
        # Given: 英数字とアンダースコアのみの文字列
        input_str = "user_name_123"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: そのまま返される
        assert result == "user_name_123"

    def test_sanitize_id_二重コロンを含む場合_アンダースコアに変換されること(self):
        # Given: "::" を含む文字列
        input_str = "namespace::class"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: "_" に変換される
        assert result == "namespace_class"

    def test_sanitize_id_記号を含む場合_アンダースコアに変換されること(self):
        # Given: スペースや記号を含む文字列
        input_str = "my-field.name/path\\test(1)[2]{3}"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: 記号が "_" に変換される
        assert result == "my_field_name_path_test_1_2_3"

    def test_sanitize_id_連続アンダースコアの場合_1つにまとめられること(self):
        # Given: 連続する "_" を含む文字列
        input_str = "field___name"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: 連続 "_" が1つにまとめられる
        assert result == "field_name"

    def test_sanitize_id_前後にアンダースコアがある場合_trimされること(self):
        # Given: 前後に "_" がある文字列
        input_str = "_field_name_"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: 前後の "_" が削除される
        assert result == "field_name"

    def test_sanitize_id_空文字列の場合_idが返されること(self):
        # Given: 空文字列
        input_str = ""

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: "id" が返される
        assert result == "id"

    def test_sanitize_id_記号のみの場合_idが返されること(self):
        # Given: 記号のみの文字列（変換後に空になる）
        input_str = "---"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: "id" が返される
        assert result == "id"

    def test_sanitize_id_数字で始まる場合_n_プレフィックスが付くこと(self):
        # Given: 数字で始まる文字列
        input_str = "123_field"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: "n_" が付加される
        assert result == "n_123_field"

    def test_sanitize_id_日本語文字列の場合_保持されること(self):
        # Given: 日本語文字列
        input_str = "ユーザー名"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: 日本語が保持される
        assert result == "ユーザー名"

    def test_sanitize_id_日本語と記号混在の場合_記号のみ変換されること(self):
        # Given: 日本語と記号が混在
        input_str = "ユーザー-名前.データ"

        # When: sanitize_idを呼ぶ
        result = MermaidNode.sanitize_id(input_str)

        # Then: 記号のみが "_" に変換される
        assert result == "ユーザー_名前_データ"

    # immutableのテスト

    def test_immutable_frozenであること(self):
        # Given: MermaidNode
        node = MermaidNode("id1", "label1", "class1")

        # When/Then: frozen=Trueによりフィールドの変更ができない
        try:
            node.node_id = "id2"  # type: ignore
            assert False, "フィールドの変更が可能になっています"
        except AttributeError:
            # 変更できないことが期待される動作
            pass
