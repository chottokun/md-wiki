import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from langchain_core.documents import Document
# 私たちがこれから作るモジュールをインポート（まだ存在しないため、テスト実行時はエラーになるはず）
try:
    from retrieval.query_engine import WikiQueryEngine
except ImportError:
    WikiQueryEngine = None

class TestWikiQueryEngine(unittest.TestCase):
    def setUp(self):
        self.mock_qdrant = MagicMock()
        self.mock_router = MagicMock()
        self.mock_model = MagicMock()
        self.mock_router.get_model.return_value = self.mock_model
        self.mock_router.get_language_instruction.return_value = "日本語で回答してください。"
        
        # テスト用の WikiQueryEngine インスタンス（未実装の場合は None）
        if WikiQueryEngine:
            self.engine = WikiQueryEngine(self.mock_qdrant, self.mock_router, wiki_dir=Path("tests/wiki_mock"))
        else:
            self.engine = None

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.read_text')
    def test_query_flow_with_links(self, mock_read, mock_exists):
        """
        検索結果にリンクが含まれている場合、その内容がコンテキストに統合されることを確認。
        """
        if self.engine is None:
            self.fail("WikiQueryEngine is not yet implemented or imported.")

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
        
        self.assertIn("LinkedConcept は重要な技術です。", prompt)
        self.assertIn("Original", prompt)
        self.assertIn("日本語で回答してください。", prompt)

    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.read_text')
    def test_query_follows_links_in_subdirectories(self, mock_read, mock_glob):
        """
        リンク先のファイルがサブディレクトリにある場合でも、再帰的に検索して取得できることを確認。
        """
        if self.engine is None:
            self.fail("WikiQueryEngine is not implemented.")

        # 1. Qdrant のモック結果 (サブディレクトリにあるはずのリンク)
        self.mock_qdrant.search.return_value = [
            Document(page_content="詳細は [[DeepConcept]] を参照。", metadata={"source": "Original", "type": "wiki_page"})
        ]
        
        # 2. Path.glob のモック (DeepConcept.md が concepts/ フォルダにあると想定)
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
        self.assertIn("DeepConcept はサブディレクトリに隠れた重要な概念です。", prompt)

if __name__ == '__main__':
    unittest.main()
