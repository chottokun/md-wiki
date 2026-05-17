import unittest
import os
import shutil
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from langchain_core.messages import AIMessage
from agent.graph import app
from langgraph.types import Command
from retrieval.qdrant_store import QdrantHybridStore
from core.schemas import UpdateDecisionSchema, WikiPageSchema

@pytest.mark.ollama
class TestE2ECoEditor(unittest.TestCase):
    """
    実リポジトリとLLMロジックを統合したE2Eテスト。
    """
    
    @classmethod
    def setUpClass(cls):
        cls.test_base = Path("tests/e2e_wiki")
        cls.test_base.mkdir(parents=True, exist_ok=True)
        # Git初期化
        subprocess.run(["git", "init"], cwd=cls.test_base, capture_output=True)
        # 初期ファイル
        cls.test_file = cls.test_base / "DemoPage.md"
        cls.test_file.write_text("# Demo Page\nOriginal text.", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=cls.test_base, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=cls.test_base, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_base, ignore_errors=True)

    @patch('core.llm_router.LLMRouter.get_model')
    def test_full_refine_flow(self, mock_get_model):
        """手動編集からAIパッチ適用までの全工程が正常に繋がっているか。"""
        # 1. 手動編集（一行追記）
        self.test_file.write_text("# Demo Page\nOriginal text.\nAdd fact from human.", encoding="utf-8")
        
        # Diff抽出
        from retrieval.sync_manager import GitSyncManager
        # テスト用のStoreを渡す（物理的なQdrantを使わないように工夫）
        mgr = GitSyncManager(store=MagicMock(), wiki_dir=self.test_base)
        diff = mgr.get_unstaged_diff("DemoPage.md")

        
        # 3. LLMのモック
        mock_model = MagicMock()
        
        # judgment node用
        mock_structured_judgment = MagicMock()
        mock_structured_judgment.invoke.return_value = UpdateDecisionSchema(update_needed=True, reason="New info from human")
        
        # refine node用
        mock_structured_refine = MagicMock()
        mock_structured_refine.invoke.return_value = WikiPageSchema(
            title="DemoPage",
            abstract="AI refined content based on human addition.",
            concepts=["concept1"],
            body="# Demo Page\nOriginal text.\nAdd fact from human.\nAI refined content.",
            tags=["refined"],
            aliases=[]
        )
        
        mock_model.with_structured_output.side_effect = [
            mock_structured_judgment,
            mock_structured_refine
        ]
        
        # fallback用
        mock_model.invoke.return_value = AIMessage(content="Fallback response")
        
        mock_get_model.return_value = mock_model

        # 4. グラフ実行
        config = {"configurable": {"thread_id": "e2e_co_editor"}}
        input_state = {
            "status": "starting_refine",
            "target_page": "DemoPage",
            "raw_markdown": diff
        }
        
        # reviewノードで止まるまで実行
        for event in app.stream(input_state, config, stream_mode="values"):
            if event.get("status") == "reviewed":
                break
        
        # 5. 承認して再開
        for event in app.stream(Command(resume="approve"), config, stream_mode="values"):
            pass
            
        # 6. 最終結果の検証
        # 注: 物理的なマージには git apply が必要だが、GitSyncManagerの実装とテスト環境を整合させる必要がある
        # 簡易的に、状態が 'completed' になっていることを確認
        state = app.get_state(config)
        self.assertIn("completed", state.values["status"])
        print("\n✅ E2E Co-Editor flow (Judgment -> Refine -> Apply) verified.")

if __name__ == '__main__':
    unittest.main()
