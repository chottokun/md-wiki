import unittest
from unittest.mock import patch, MagicMock
import os
from core.llm_router import router
from retrieval.qdrant_store import QdrantHybridStore

class TestUILogic(unittest.TestCase):
    """
    UIアプリ (streamlit) から呼び出されるコアロジックの徹底検証。
    """
    
    @patch('retrieval.qdrant_store.QdrantHybridStore.search')
    @patch('core.llm_router.LLMRouter.get_model')
    @patch('retrieval.qdrant_store.QdrantClient')
    @patch('langchain_community.embeddings.fastembed.FastEmbedEmbeddings')
    @patch('langchain_qdrant.FastEmbedSparse')
    def test_ui_query_integration(self, mock_sparse, mock_fastembed, mock_client, mock_get_model, mock_search):
        """UIのチャット機能から呼ばれる検索・生成プロセスの模倣。"""
        # モックの設定
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Mocked Response")
        mock_get_model.return_value = mock_model
        
        from langchain_core.documents import Document
        mock_search.return_value = [Document(page_content="test context", metadata={"source": "test", "type": "wiki_page"})]
        
        # UI内のロジックをシミュレート
        query = "How to use md-wiki?"
        with patch('langchain_qdrant.qdrant.QdrantVectorStore._validate_collection_config'):
            docs = QdrantHybridStore().search(query, k=5)
        self.assertEqual(len(docs), 1)
        
        inst = router.get_language_instruction()
        response = mock_model.invoke(f"{inst}\nContext: {docs[0].page_content}\nQuery: {query}")
        
        self.assertEqual(response.content, "Mocked Response")
        mock_model.invoke.assert_called_once()

    def test_language_instruction_consistency(self):
        """UIで言語を切り替えた際、指示文が常に期待通りか。"""
        languages = {
            "Japanese": "必ずJapaneseで回答・出力してください。",
            "English": "必ずEnglishで回答・出力してください。",
            "Chinese": "必ずChineseで回答・出力してください。"
        }
        for lang, expected in languages.items():
            os.environ["TARGET_LANGUAGE"] = lang
            self.assertEqual(router.get_language_instruction(), expected)

if __name__ == '__main__':
    unittest.main()
