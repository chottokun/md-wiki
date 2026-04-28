import unittest
import os
from pathlib import Path
from core.llm_router import router
from retrieval.qdrant_store import QdrantHybridStore
from ingestion.docling_parser import DoclingParser

class TestSystemRobustness(unittest.TestCase):
    def test_language_enforcement(self):
        """環境変数による指示言語の変更が正しく反映されるか。"""
        os.environ["TARGET_LANGUAGE"] = "English"
        inst = router.get_language_instruction()
        self.assertIn("English", inst)
        
        os.environ["TARGET_LANGUAGE"] = "Japanese"
        inst = router.get_language_instruction()
        self.assertIn("Japanese", inst)

    def test_invalid_file_ingestion(self):
        """存在しないファイルや非対応形式のハンドリング。"""
        parser = DoclingParser()
        # 存在しないファイル
        res = parser.convert("ghost.pdf")
        self.assertIsNone(res)
        # 壊れたパス
        res = parser.convert("")
        self.assertIsNone(res)

    def test_qdrant_metadata_filtering(self):
        """Qdrantでのメタデータによるフィルタリング（Raw vs Wiki）が機能する準備。"""
        store = QdrantHybridStore(collection_name="robust_test")
        from langchain_core.documents import Document
        docs = [
            Document(page_content="Fact A", metadata={"type": "raw_source", "source": "src1"}),
            Document(page_content="Summary A", metadata={"type": "wiki_page", "source": "src1"}),
        ]
        store.add_documents(docs)
        
        # 検索結果にメタデータが含まれていることの確認
        results = store.search("Fact A", k=1)
        self.assertEqual(results[0].metadata["type"], "raw_source")
        
        store.delete_collection()

    def test_chunk_configuration(self):
        """環境変数のチャンクサイズ設定が反映されるか。"""
        os.environ["CHUNK_SIZE"] = "123"
        os.environ["CHUNK_OVERLAP"] = "10"
        
        store = QdrantHybridStore(collection_name="chunk_config_test")
        # 内部的な splitter は add_text 時に生成されるため、メソッド呼び出しで確認
        store.add_text("A" * 500, {"source": "test"})
        
        # 123文字程度に分割されているはず
        results = store.search("A", k=10)
        # 少なくとも 500/123 = 4つ以上のドキュメントがあるはず
        self.assertTrue(len(results) >= 4)
        
        store.delete_collection()

if __name__ == '__main__':
    unittest.main()
