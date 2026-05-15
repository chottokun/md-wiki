import unittest
import os
import logging
from pathlib import Path
from langchain_core.documents import Document
from retrieval.qdrant_store import QdrantHybridStore
from qdrant_client import QdrantClient
import pytest

# テスト用の設定
COLLECTION_NAME = "test_collection"

@pytest.mark.ollama
class TestQdrantHybridStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 現在の実装に合わせて初期化 (url引数は削除されている)
        cls.store = QdrantHybridStore(collection_name=COLLECTION_NAME)

    @classmethod
    def tearDownClass(cls):
        # テスト用コレクションの削除
        cls.store.delete_collection()

    def test_add_and_search(self):
        # ドキュメントの追加
        docs = [
            Document(page_content="Gemini CLI is a powerful tool for developers.", metadata={"source": "doc1"}),
            Document(page_content="RAG-wiki uses LangChain and Qdrant.", metadata={"source": "doc2"}),
        ]
        self.store.add_documents(docs)
        
        # 検索のテスト
        results = self.store.search("What is Gemini CLI?")
        self.assertTrue(len(results) > 0)
        self.assertIn("Gemini CLI", results[0].page_content)

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

    def test_sync_from_disk_logic(self):
        # sync_from_disk の引数が変更されているため、現在のロジックに合わせてテスト
        # 内部で self.wiki_dir を参照するため、一時的にディレクトリを作成
        test_wiki_dir = Path("wiki_test_sync")
        test_wiki_dir.mkdir(exist_ok=True)
        (test_wiki_dir / "TestPage.md").write_text("Sync content", encoding="utf-8")
        
        original_wiki_dir = self.store.wiki_dir
        self.store.wiki_dir = test_wiki_dir
        
        try:
            self.store.sync_from_disk(include_unreviewed=True)
            res = self.store.search("Sync content")
            self.assertTrue(any("Sync content" in d.page_content for d in res))
        finally:
            self.store.wiki_dir = original_wiki_dir
            shutil = __import__("shutil")
            shutil.rmtree(test_wiki_dir, ignore_errors=True)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
