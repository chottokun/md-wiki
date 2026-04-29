import unittest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.abspath(os.curdir))

class RealTestMocked(unittest.TestCase):
    """
    Ollamaが動作していない環境でも、リファクタリング後の main.run_query が
    正しく WikiQueryEngine を介して動作することを確認する「実テスト」の代用。
    """

    @patch('main.qdrant_store')
    @patch('main.router')
    @patch('retrieval.query_engine.Path.exists')
    @patch('retrieval.query_engine.Path.read_text')
    def test_run_query_integration(self, mock_read, mock_exists, mock_router, mock_qdrant):
        # 1. 依存関係のモック化
        mock_qdrant.search.return_value = [
            Document(page_content="RAGについてのWikiページ。 [[RAG_Detail]] も参照。", 
                     metadata={"source": "RAG_Intro", "type": "wiki_page"})
        ]
        
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="RAGは検索拡張生成の略です。詳細はWikiにあります。")
        mock_router.get_model.return_value = mock_model
        mock_router.get_language_instruction.return_value = "日本語で答えてください。"
        
        # リンク先が存在すると設定
        mock_exists.return_value = True
        mock_read.return_value = "RAG_Detail: Retrieval-Augmented Generation の詳細解説。"

        # 2. main.run_query の実行
        # ここでリファクタリング後の WikiQueryEngine が内部で呼ばれる
        from main import run_query
        print("\n--- Start Real-style Mock Test ---")
        run_query("RAGとは？")
        print("--- End Real-style Mock Test ---\n")

        # 3. 検証
        # WikiQueryEngine がリンク先の内容を読み取ったか確認
        self.assertTrue(mock_read.called)
        
        # LLM に渡されたプロンプトにリンク先の内容が含まれているか確認
        args, _ = mock_model.invoke.call_args
        prompt = args[0]
        self.assertIn("RAG_Detail", prompt)
        self.assertIn("Retrieval-Augmented Generation", prompt)
        self.assertIn("日本語で答えてください。", prompt)
        
        print("✅ リファクタリング後の main.run_query が WikiQueryEngine を正しく利用していることが確認されました。")

if __name__ == '__main__':
    unittest.main()
