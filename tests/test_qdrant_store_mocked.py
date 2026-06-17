import unittest
from unittest.mock import MagicMock, patch
from retrieval.qdrant_store import QdrantHybridStore
from langchain_core.embeddings import Embeddings
from qdrant_client.http import models as rest_models

class MockEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[0.1] * 1024 for _ in texts]
    def embed_query(self, text):
        return [0.1] * 1024

class TestQdrantHybridStoreMocked(unittest.TestCase):
    def setUp(self):
        import os
        os.environ["QDRANT_MODE"] = "memory"
        os.environ["SKIP_SPARSE_EMBEDDINGS"] = "true"
        
        with patch("retrieval.qdrant_store.QdrantClient") as mock_client:
            # 必要な属性をすべてモック
            mock_col_info = MagicMock()
            mock_col_info.config.params.vectors.size = 1024
            mock_col_info.config.params.vectors.distance = rest_models.Distance.COSINE
            mock_client.return_value.get_collection.return_value = mock_col_info
            mock_client.return_value.collection_exists.return_value = True
            
            with patch("retrieval.qdrant_store.OllamaEmbeddings", return_value=MockEmbeddings()):
                with patch("langchain_community.embeddings.fastembed.FastEmbedEmbeddings", return_value=MockEmbeddings()):
                    with patch("langchain_qdrant.FastEmbedSparse") as mock_sparse:
                        # QdrantVectorStoreのバリデーションを回避するために一部モック化
                        with patch("langchain_qdrant.qdrant.QdrantVectorStore._validate_collection_config"):
                            self.store = QdrantHybridStore()

    @patch("langchain_text_splitters.RecursiveCharacterTextSplitter.split_text")
    def test_add_text_uses_splitter(self, mock_split):
        mock_split.return_value = ["chunk1", "chunk2"]
        # vector_storeをモック
        self.store.vector_store = MagicMock()
        
        self.store.add_text("dummy text", metadata={"source": "test"})
        
        mock_split.assert_called_once_with("dummy text")
        self.assertEqual(self.store.vector_store.add_documents.call_count, 1)

    def test_initialization_sets_splitter(self):
        self.assertIsNotNone(self.store.text_splitter)
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        self.assertIsInstance(self.store.text_splitter, RecursiveCharacterTextSplitter)

if __name__ == "__main__":
    unittest.main()
