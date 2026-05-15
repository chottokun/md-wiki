import unittest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from retrieval.query_engine import WikiQueryEngine
from pathlib import Path

class TestWikiQueryEngine(unittest.TestCase):
    def setUp(self):
        self.mock_qdrant = MagicMock()
        self.mock_router = MagicMock()
        self.mock_model = MagicMock()
        self.mock_router.get_model.return_value = self.mock_model
        # システムプロンプト作成時に呼ばれる router.get_language_instruction
        self.mock_router.get_language_instruction.return_value = "日本語で回答してください。"
        
        # テスト対象
        self.engine = WikiQueryEngine(self.mock_qdrant, self.mock_router)

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.read_text')
    def test_query_flow_with_links(self, mock_read, mock_exists):
        """
        検索結果にリンクが含まれている場合、その内容もコンテキストに統合されることを確認。
        """
        # 1. Qdrant のモック結果
        self.mock_qdrant.search.return_value = [
            Document(page_content="詳細は [[LinkedConcept]] を参照。", metadata={"source": "Original", "type": "wiki_page"})
        ]

        # 2. リンク先ファイルのモック
        mock_exists.return_value = True
        mock_read.return_value = "LinkedConcept は重要な技術です。"

        # 3. LLM の応答モック
        self.mock_model.invoke.return_value = MagicMock(content="回答結果です。")

        # 4. 実行
        result = self.engine.query("テストクエリ")

        # 5. 検証
        self.assertEqual(result, "回答結果です。")

        # invoke に渡されたプロンプトを確認
        args, _ = self.mock_model.invoke.call_args
        prompt = args[0]
        
        # プロンプトがリスト形式（(role, content)）であることを前提に文字列化してチェック
        prompt_str = str(prompt)

        self.assertIn("LinkedConcept は重要な技術です。", prompt_str)

    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.read_text')
    def test_query_follows_links_in_subdirectories(self, mock_read, mock_glob):
        """
        リンク先ファイルがサブディレクトリにある場合でも、再帰的に検索して取得できることを確認。
        """
        # 1. Qdrant のモック結果
        self.mock_qdrant.search.return_value = [
            Document(page_content="詳細は [[DeepConcept]] を参照。", metadata={"source": "Original", "type": "wiki_page"})
        ]

        # 2. Path.glob のモック
        mock_deep_path = MagicMock(spec=Path)
        mock_deep_path.name = "DeepConcept.md"
        mock_deep_path.stem = "DeepConcept"
        mock_deep_path.exists.return_value = True
        mock_deep_path.read_text.return_value = "DeepConcept はサブディレクトリに隠れた重要な概念です。"
        mock_glob.return_value = [mock_deep_path]

        # 3. LLM の応答モック
        self.mock_model.invoke.return_value = MagicMock(content="回答結果。")

        # 4. 実行
        self.engine.query("テスト")

        # 5. 検証
        args, _ = self.mock_model.invoke.call_args
        prompt = args[0]
        prompt_str = str(prompt)
        self.assertIn("DeepConcept はサブディレクトリに隠れた重要な概念です。", prompt_str)

if __name__ == '__main__':
    unittest.main()
