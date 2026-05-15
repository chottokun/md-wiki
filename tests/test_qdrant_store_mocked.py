import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Mock all dependencies
mock_modules = [
    "langchain_core",
    "langchain_core.documents",
    "langchain_qdrant",
    "langchain_ollama",
    "qdrant_client",
    "qdrant_client.http",
    "langchain_text_splitters",
    "dotenv"
]

for mod in mock_modules:
    sys.modules[mod] = MagicMock()

import langchain_core.documents
langchain_core.documents.Document = MagicMock

from retrieval.qdrant_store import QdrantHybridStore

class TestQdrantHybridStoreMocked(unittest.TestCase):
    def setUp(self):
        self.store = QdrantHybridStore(collection_name="test_collection")
        self.store.add_documents = MagicMock()

    def test_add_text_uses_splitter(self):
        text = "Hello world. This is a test."
        metadata = {"source": "test"}

        # We need to make sure self.store.text_splitter.split_text returns something
        self.store.text_splitter.split_text.return_value = ["Hello world.", "This is a test."]

        self.store.add_text(text, metadata)

        self.store.text_splitter.split_text.assert_called_with(text)
        self.assertEqual(self.store.add_documents.call_count, 1)

    def test_initialization_sets_splitter(self):
        self.assertIsNotNone(self.store.text_splitter)
        # Check if RecursiveCharacterTextSplitter was called with expected arguments
        # Since it's mocked, we check the mock call
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        RecursiveCharacterTextSplitter.assert_called()

if __name__ == "__main__":
    unittest.main()
