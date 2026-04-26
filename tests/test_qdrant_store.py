import unittest
import os
import logging
from pathlib import Path
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

    def test_sync_from_disk(self):
        # テスト用のファイル配置
        test_wiki_dir = Path("tests/test_wiki_sync")
        test_raw_md_dir = Path("tests/test_wiki_sync/raw_markdown")
        test_wiki_dir.mkdir(parents=True, exist_ok=True)
        test_raw_md_dir.mkdir(parents=True, exist_ok=True)
        
        (test_wiki_dir / "WikiPage.md").write_text("Detailed wiki content", encoding="utf-8")
        (test_raw_md_dir / "RawPage_raw.md").write_text("Raw fact content", encoding="utf-8")
        
        # 同期実行
        self.store.sync_from_disk(wiki_dir=str(test_wiki_dir), raw_md_dir=str(test_raw_md_dir))
        
        # 検索して反映を確認
        res1 = self.store.search("Detailed wiki content", k=1)
        self.assertEqual(res1[0].metadata["type"], "wiki_page")
        
        res2 = self.store.search("Raw fact content", k=1)
        self.assertEqual(res2[0].metadata["type"], "raw_source")
        
        # クリーンアップ
        import shutil
        shutil.rmtree(test_wiki_dir)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
