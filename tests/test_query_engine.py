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
        self.engine = WikiQueryEngine(self.mock_qdrant, self.mock_router, wiki_dir=Path("fake_wiki"))

    @patch('os.walk')
    @patch('pathlib.Path.read_text')
    def test_query_flow_with_links(self, mock_read, mock_walk):
        """
        検索結果にリンクが含まれている場合、その内容もコンテキストに統合されることを確認。
        """
        # 1. Qdrant のモック結果
        self.mock_qdrant.search.return_value = [
            Document(page_content="詳細は [[LinkedConcept]] を参照。", metadata={"source": "Original", "type": "wiki_page"})
        ]

        # 2. リンク先ファイルのモック
        mock_walk.return_value = [
            ("fake_wiki", [], ["LinkedConcept.md"])
        ]
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
        prompt_str = str(prompt)
        
        self.assertIn("LinkedConcept は重要な技術です。", prompt_str)
        self.assertIn("Original", prompt_str)
        self.assertIn("日本語で回答してください。", prompt_str)

    @patch('os.walk')
    @patch('pathlib.Path.read_text')
    def test_query_follows_links_in_subdirectories(self, mock_read, mock_walk):
        """
        リンク先ファイルがサブディレクトリにある場合でも、再帰的に検索して取得できることを確認。
        """
        # 1. Qdrant のモック結果
        self.mock_qdrant.search.return_value = [
            Document(page_content="詳細は [[DeepConcept]] を参照。", metadata={"source": "Original", "type": "wiki_page"})
        ]

        # 2. os.walk のモック
        mock_walk.return_value = [
            ("fake_wiki/subdir", [], ["DeepConcept.md"])
        ]
        mock_read.return_value = "DeepConcept はサブディレクトリに隠れた重要な概念です。"

        # 3. LLM の応答モック
        self.mock_model.invoke.return_value = MagicMock(content="回答結果。")

        # 4. 実行
        self.engine.query("テスト")

        # 5. 検証
        args, _ = self.mock_model.invoke.call_args
        prompt = args[0]
        prompt_str = str(prompt)
        self.assertIn("DeepConcept はサブディレクトリに隠れた重要な概念です。", prompt_str)

    @patch('os.walk')
    def test_wiki_index_caching(self, mock_walk):
        """
        _wiki_index がキャッシュされ、os.walk の呼び出しが1回のみであることを検証。
        """
        mock_walk.return_value = []
        
        # 初回アクセス
        idx1 = self.engine._wiki_index
        # 2回目アクセス
        idx2 = self.engine._wiki_index
        
        self.assertIs(idx1, idx2)
        mock_walk.assert_called_once()

    @patch('os.walk')
    def test_wiki_index_duplicate_prioritization(self, mock_walk):
        """
        重複する stem がある場合、concepts ディレクトリが最優先され、raw_markdown が最低限にされることを検証。
        """
        # 1. raw_markdown と references の場合、references が優先
        engine1 = WikiQueryEngine(self.mock_qdrant, self.mock_router, wiki_dir=Path("fake_wiki"))
        mock_walk.return_value = [
            ("fake_wiki/raw_markdown", [], ["BERT.md"]),
            ("fake_wiki/references", [], ["BERT.md"])
        ]
        idx1 = engine1._wiki_index
        self.assertIn("BERT", idx1)
        self.assertIn("references", str(idx1["BERT"]))

        # 2. references と concepts の場合、concepts が優先
        engine2 = WikiQueryEngine(self.mock_qdrant, self.mock_router, wiki_dir=Path("fake_wiki"))
        mock_walk.return_value = [
            ("fake_wiki/references", [], ["BERT.md"]),
            ("fake_wiki/concepts", [], ["BERT.md"])
        ]
        idx2 = engine2._wiki_index
        self.assertIn("BERT", idx2)
        self.assertIn("concepts", str(idx2["BERT"]))

if __name__ == '__main__':
    unittest.main()
