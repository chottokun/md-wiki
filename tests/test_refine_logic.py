import pytest
from unittest.mock import patch, MagicMock
from retrieval.sync_manager import GitSyncManager
from retrieval.qdrant_store import QdrantHybridStore
from pathlib import Path
import git

def test_extract_unstaged_diff(tmp_path):
    """unstagedな変更をgit diffで正しく抽出できるか。"""
    # 1. テスト用リポジトリの初期化
    repo_dir = tmp_path / "wiki"
    repo_dir.mkdir()
    repo = git.Repo.init(repo_dir)
    
    # ダミーファイルの作成とコミット
    test_file = repo_dir / "Page.md"
    test_file.write_text("Old info", encoding="utf-8")
    repo.index.add(["Page.md"])
    repo.index.commit("Initial")
    
    # ファイルの変更（unstaged）
    test_file.write_text("New factual info", encoding="utf-8")
    
    # 2. SyncManagerの初期化
    mock_store = MagicMock(spec=QdrantHybridStore)
    with patch("core.config.Config.WIKI_DIR", repo_dir):
        mgr = GitSyncManager(store=mock_store)
        diff = mgr.get_unstaged_diff("Page.md")
        
        # 3. 検証
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
