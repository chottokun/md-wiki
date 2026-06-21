import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json

from agent.state import AgentState

# Import synthesis_node from agent.graph
from agent.graph import synthesis_node

class TestSynthesisNode(unittest.TestCase):
    @patch("agent.graph.get_qdrant_store")
    @patch("agent.graph.router")
    def test_synthesis_node_success(self, mock_router, mock_get_qdrant_store):
        # Setup mock Qdrant store
        mock_store = MagicMock()
        mock_get_qdrant_store.return_value = mock_store
        
        doc1 = MagicMock()
        doc1.page_content = "RAG is retrieval augmented generation."
        doc1.metadata = {"source": "source_a.pdf"}
        mock_store.search.return_value = [doc1]

        # Setup mock LLM model
        mock_llm = MagicMock()
        mock_router.get_model.return_value = mock_llm
        
        # Invoke result for LLM
        mock_response = MagicMock()
        mock_response.content = "# RAG\n\n> [!abstract] 要約\nThis is synthesis body."
        
        mock_structured_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm
        
        # Metadata response
        from core.schemas import WikiMetadataSchema
        metadata = WikiMetadataSchema(
            title="RAG",
            description="This is synthesis body.",
            concepts=["RAG"],
            tags=["AI", "RAG"],
            aliases=[]
        )
        mock_structured_llm.invoke.return_value = metadata
        mock_llm.invoke.return_value = mock_response

        # Execute
        state = {
            "maintenance_topic": "RAG",
            "retrieved_docs": [],
            "proposed_data": None,
            "proposed_content": None,
            "target_page": None,
            "status": "starting"
        }
        
        result = synthesis_node(state)

        # Verify
        self.assertEqual(result["status"], "synthesized")
        self.assertEqual(result["target_page"], "rag")
        self.assertIsNotNone(result["proposed_content"])
        self.assertEqual(result["proposed_data"]["title"], "rag")
        self.assertEqual(result["proposed_data"]["abstract"], "This is synthesis body.")
        self.assertIn("maintenance", result["proposed_data"]["tags"])

if __name__ == "__main__":
    unittest.main()
