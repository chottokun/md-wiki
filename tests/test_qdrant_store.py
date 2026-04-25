import unittest
import os
import logging
from langchain_core.documents import Document
from retrieval.qdrant_store import QdrantHybridStore
from qdrant_client import QdrantClient

# テスト用の設定
COLLECTION_NAME = "test_collection"
QDRANT_URL = "http://localhost:6333"

class TestQdrantHybridStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # コンストラクタ内で自動的にコレクションが作成されることをテスト
        cls.store = QdrantHybridStore(collection_name=COLLECTION_NAME, url=QDRANT_URL)

    @classmethod
    def tearDownClass(cls):
        # テスト用コレクションの削除
        cls.store.delete_collection()

    def test_add_and_search(self):
        # ドキュメントの追加
        docs = [
            Document(page_content="Gemini CLI is a powerful tool for developers.", metadata={"source": "doc1"}),
            Document(page_content="RAG-wiki uses LangChain and Qdrant.", metadata={"source": "doc2"}),
            Document(page_content="Hybrid search combines dense and sparse vectors.", metadata={"source": "doc3"}),
        ]
        self.store.add_documents(docs)
        
        # 検索のテスト
        results = self.store.search("What is Gemini CLI?")
        self.assertTrue(len(results) > 0)
        self.assertIn("Gemini CLI", results[0].page_content)
        
        # ハイブリッド検索（キーワード）のテスト
        results = self.store.search("RAG-wiki")
        self.assertTrue(any("RAG-wiki" in doc.page_content for doc in results))

    def test_add_text_chunking(self):
        # 長いテキストを追加
        long_text = "This is a long sentence. " * 50
        
        # CHUNK_SIZEを環境変数で設定してテスト
        os.environ["CHUNK_SIZE"] = "50"
        os.environ["CHUNK_OVERLAP"] = "10"
        
        self.store.add_text(long_text, {"source": "chunk_doc"})
        
        results = self.store.search("long sentence")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].metadata["source"], "chunk_doc")
        self.assertTrue(len(results[0].page_content) <= 100) # オーバーラップ等を考慮して多少の余裕を持つ

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
