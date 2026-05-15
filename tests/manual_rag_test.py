import os
import sys
import io

import pytest
sys.path.append(os.getcwd())
from retrieval.qdrant_store import QdrantHybridStore
from core.llm_router import router, LLMLayer

@pytest.mark.ollama
def test_rag_query():
    with open("tests/rag_result.txt", "w", encoding="utf-8") as f:
        store = QdrantHybridStore()
        query = "SELF-RAGにおけるISRELとISSUPの違いを教えてください。"
        f.write(f"Query: {query}\n")
        
        docs = store.search(query, k=5)
        f.write(f"\n[Retrieval] Found {len(docs)} documents.\n")
        for i, d in enumerate(docs):
            src = d.metadata.get("source", "unknown")
            f.write(f"  - Source {i+1}: {src}\n")
        
        llm = router.get_model(LLMLayer.L2)
        context = "\n\n".join([d.page_content for d in docs])
        prompt = f"以下のコンテキストに基づいて、ISRELとISSUPの違いを日本語で詳しく説明してください。\n\nコンテキスト:\n{context}"
        
        response = llm.invoke(prompt)
        f.write(f"\n[Generation] Response:\n{response.content}\n")

if __name__ == "__main__":
    test_rag_query()
