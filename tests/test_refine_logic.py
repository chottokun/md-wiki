import pytest
import unittest
from unittest.mock import patch, MagicMock
from retrieval.sync_manager import GitSyncManager
from retrieval.qdrant_store import QdrantHybridStore
from pathlib import Path
import git

class TestRefineLogic(unittest.TestCase):
    """
    手動編集(git diff)をきっかけとしたAIによる自動改善提案フローの検証。
    """

    @patch('git.Repo')
    def test_extract_unstaged_diff(self, mock_repo):
        """unstagedな変更をgit diffで正しく抽出できるか。"""
        # Repo().git.diff('HEAD', '--', 'Page.md') の戻り値を設定
        mock_git = mock_repo.return_value.git
        mock_git.diff.return_value = "--- a/wiki/Page.md\n+++ b/wiki/Page.md\n@@ -1,2 +1,2 @@\n-Old info\n+New factual info"
        
        mgr = GitSyncManager(store=MagicMock())
        diff = mgr.get_unstaged_diff("Page.md")
        
        # 3. 検証
        mock_git.diff.assert_called_once_with('HEAD', '--', 'Page.md')
        assert "New factual info" in diff
        assert "+New factual info" in diff

def test_refine_proposal_generation():
    """
    LLMへのプロンプトにdiffが含まれているか。
    """
    # 実際には agent/graph.py の refine_node で行われるが、
    # ここではその周辺ロジックのみ検証
    from core.prompts import get_refine_prompt
    prompt = get_refine_prompt("TestPage", "Current", "Diff", "Inst")
    
    # プロンプト（リスト形式）の内容チェック
    prompt_str = str(prompt)
    assert "Diff" in prompt_str
    assert "Current" in prompt_str
