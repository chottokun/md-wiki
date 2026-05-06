import unittest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from main import run_query
import os

class TestLinkAwareQuery(unittest.TestCase):
    """
    質問回答時（Query Mode）において、リンク関係性が正しく活用されているかの検証。
    """

    @patch('retrieval.qdrant_store.QdrantHybridStore.search')
    @patch('core.llm_router.LLMRouter.get_model')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.read_text')
    def test_query_follows_wiki_links(self, mock_read, mock_exists, mock_get_model, mock_search):
        """
        検索結果に [[LinkedPage]] が含まれる場合、その内容もコンテキストに追加されるか。
        """
        # 1. 初期検索結果（リンク付きページ）
        mock_search.return_value = [
            Document(page_content="See [[Chain-of-Thought]] for details.", metadata={"source": "OriginalPage", "type": "wiki_page"})
        ]
        
        # 2. リンク先ページが存在し、内容を返すと設定
        mock_exists.return_value = True
        mock_read.return_value = "Chain-of-Thought is a prompting technique."
        
        # 3. LLMのモック
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model
        
        # 4. 実行
        from main import run_query
        # 内部で print が走るため、キャプチャなしでロジック通過を確認
        run_query("Tell me about Chain-of-Thought")
        
        # 検証：リンク先のファイル読み込みが試行されたか
        # get_model のプロンプト構築時に、リンク先の内容が含まれているはず
        args, kwargs = mock_model.invoke.call_args
        prompt_content = args[0]
        
        self.assertIn("Chain-of-Thought is a prompting technique.", prompt_content)
        self.assertIn("OriginalPage", prompt_content)
        logger_info = "Link-aware query succeeded in finding linked context."
        print(f"\n✅ {logger_info}")

if __name__ == '__main__':
    unittest.main()
