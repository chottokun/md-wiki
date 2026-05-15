import unittest
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document

@pytest.mark.ollama
class TestLinkAwareQuery(unittest.TestCase):
    """
    質問回答時（Query Mode）において、リンク関係性が正しく活用されているかの検証。
    """

    def setUp(self):
        # 環境変数の設定
        import os
        os.environ["QDRANT_MODE"] = "memory"
        os.environ["SKIP_SPARSE_EMBEDDINGS"] = "true"

    @patch('agent.graph.get_qdrant_store')
    @patch('core.llm_router.LLMRouter.get_model')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.read_text')
    def test_query_follows_wiki_links(self, mock_read, mock_exists, mock_get_model, mock_get_store):
        """
        検索結果に [[LinkedPage]] が含まれる場合、その内容もコンテキストに追加されるか。
        """
        # 1. QdrantStoreのモック
        mock_store = mock_get_store.return_value
        mock_store.search.return_value = [
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
        
        # 検証：invoke が呼ばれたことを確認
        self.assertTrue(mock_model.invoke.called)
        
        # get_model のプロンプト構築時に、リンク先の内容が含まれているはず
        args, kwargs = mock_model.invoke.call_args
        # プロンプトはリスト形式の場合と文字列形式の場合がある
        prompt_data = args[0]
        if isinstance(prompt_data, list):
            prompt_content = str(prompt_data)
        else:
            prompt_content = prompt_data
        
        self.assertIn("Chain-of-Thought is a prompting technique.", prompt_content)
        self.assertIn("OriginalPage", prompt_content)
        print("\n✅ Link-aware query succeeded in finding linked context.")

if __name__ == '__main__':
    unittest.main()
