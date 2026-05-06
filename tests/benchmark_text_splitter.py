import time
import os
import sys
from unittest.mock import MagicMock

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

# Define a fake RecursiveCharacterTextSplitter
class FakeRecursiveCharacterTextSplitter:
    def __init__(self, chunk_size, chunk_overlap, separators):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators
        # Simulate some initialization overhead (reading env vars and object creation)
        time.sleep(0.0001)

    def split_text(self, text):
        return [text[i:i+self.chunk_size] for i in range(0, len(text), self.chunk_size)]

sys.modules["langchain_text_splitters"].RecursiveCharacterTextSplitter = FakeRecursiveCharacterTextSplitter

from retrieval.qdrant_store import QdrantHybridStore

def benchmark():
    os.environ["CHUNK_SIZE"] = "400"
    os.environ["CHUNK_OVERLAP"] = "50"

    store = QdrantHybridStore(collection_name="benchmark_collection")
    store.add_documents = MagicMock()

    text = "This is a sample text. " * 100
    metadata = {"source": "benchmark"}
    iterations = 1000

    # 1. Baseline (simulating the OLD way: init splitter every time)
    start_time = time.time()
    for _ in range(iterations):
        # Simulate the old add_text logic
        ts = FakeRecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "、", " ", ""]
        )
        chunks = ts.split_text(text)
        # documents = [Document(page_content=chunk, metadata=metadata) for chunk in chunks]
        store.add_documents([])
    end_time = time.time()
    baseline_time = end_time - start_time

    # 2. Optimized (calling the NEW implementation)
    start_time = time.time()
    for _ in range(iterations):
        store.add_text(text, metadata)
    end_time = time.time()
    optimized_time = end_time - start_time

    print(f"Baseline (Old Way) - Total time: {baseline_time:.4f}s, Avg: {baseline_time/iterations:.6f}s")
    print(f"Optimized (New Way) - Total time: {optimized_time:.4f}s, Avg: {optimized_time/iterations:.6f}s")
    improvement = (baseline_time - optimized_time) / baseline_time * 100
    print(f"Improvement: {improvement:.2f}%")

if __name__ == "__main__":
    benchmark()
