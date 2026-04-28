import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from retrieval.sync_manager import GitSyncManager

class TestRefineLogic(unittest.TestCase):
    """
    手動編集(git diff)をきっかけとしたAIによる自動改善提案フローの検証。
    """

    @patch('subprocess.run')
    def test_extract_unstaged_diff(self, mock_run):
        """unstagedな変更をgit diffで正しく抽出できるか。"""
        mock_run.return_value = MagicMock(
            stdout="--- a/wiki/Page.md\n+++ b/wiki/Page.md\n@@ -1,2 +1,2 @@\n-Old info\n+New factual info",
            returncode=0
        )
        
        from retrieval.qdrant_store import QdrantHybridStore
        mgr = GitSyncManager(store=MagicMock())
        diff = mgr.get_unstaged_diff("Page.md")
        
        self.assertIn("+New factual info", diff)
        self.assertIn("-Old info", diff)

    @patch('core.llm_router.LLMRouter.get_model')
    def test_refine_proposal_generation(self, mock_get_model):
        """diffを見てLLMが適切な修正案（パッチ）を作成するか。"""
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="## 修正案\nこの要約を更新しました。\n\n[Full Content...]")
        mock_get_model.return_value = mock_model
        
        # 擬似的な入力
        diff_input = "User added: info about RAG-Agent."
        target_content = "# RAG Page\nOld summary."
        
        # 実際の実装予定プロンプトのシミュレーション
        from core.llm_router import router
        inst = router.get_language_instruction()
        prompt = f"{inst}\n以下の差分を見て、Wikiページを最適化してください。\nDiff: {diff_input}\nBase: {target_content}"
        
        res = mock_model.invoke(prompt)
        self.assertIn("修正案", res.content)

if __name__ == '__main__':
    unittest.main()
