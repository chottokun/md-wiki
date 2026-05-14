import unittest
from unittest.mock import patch, MagicMock
from agent.graph import app

class TestConflictResolution(unittest.TestCase):
    """
    Gitコンフリクトマーカーを含むテキストに対するAI解決フローの検証。
    """

    @patch('core.llm_router.LLMRouter.get_model')
    def test_conflict_trigger_and_resolve(self, mock_get_model):
        """衝突マーカーを検知してconflictノードが呼ばれ、解決案が生成されるか。"""
        # 1. 衝突を含む入力
        conflict_text = """
<<<<<<< HEAD
RAGは検索拡張生成の略称です。
=======
Retrieval-Augmented Generation (RAG) は外部知識を活用します。
>>>>>>> branch-v2
        """
        
        # 2. LLMのモック
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Retrieval-Augmented Generation (RAG) は、外部知識を活用する検索拡張生成の略称です。")
        
        # structured_output のモック
        mock_structured_llm = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured_llm
        
        # model_dump() がシリアライズ可能な辞書を返すようにする
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "title": "RAG_Intro",
            "abstract": "RAGの概要",
            "concepts": ["RAG"],
            "body": "Retrieval-Augmented Generation (RAG) は、外部知識を活用する検索拡張生成の略称です。",
            "tags": ["conflict-resolved"],
            "aliases": []
        }
        mock_structured_llm.invoke.return_value = mock_result
        
        mock_get_model.return_value = mock_model
        
        # 3. ワークフロー開始
        config = {"configurable": {"thread_id": "conflict_test"}}
        # router_entry が 'conflict' を返すことを期待
        input_state = {
            "status": "starting_conflict",
            "raw_markdown": conflict_text, 
            "target_page": "RAG_Intro"
        }
        for event in app.stream(input_state, config, stream_mode="values"):
            if event.get("status") == "resolved":
                break
        
        # 4. 検証
        state = app.get_state(config)
        self.assertEqual("resolved", state.values["status"])
        self.assertIn("RAG) は、外部知識を", state.values["proposed_data"]["body"])
        print("\n✅ Conflict resolution logic verified via LLM synthesis.")

if __name__ == '__main__':
    unittest.main()
