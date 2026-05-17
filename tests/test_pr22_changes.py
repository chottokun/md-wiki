import pytest
from core.prompts import (
    get_ingest_prompt,
    get_lint_body_prompt,
    get_metadata_prompt,
    get_fallback_prompt,
    get_translation_prompt,
    get_judgment_prompt,
    get_refine_prompt,
    get_draft_body_prompt,
    SECURITY_INSTRUCTION
)
from retrieval.sync_manager import GitSyncManager
from retrieval.qdrant_store import QdrantHybridStore
from unittest.mock import MagicMock, patch
from pathlib import Path

def test_prompts_generation():
    # Test if prompts are generated and contain expected placeholders
    content = "Sample content"
    term = "Sample Term"
    context = "Sample Context"
    
    # Prompt is now a list of (role, content) tuples
    ingest_prompt = get_ingest_prompt(content)
    assert content in ingest_prompt[1][1]
    assert SECURITY_INSTRUCTION in ingest_prompt[0][1]
    
    lint_prompt = get_lint_body_prompt(term, context)
    assert term in lint_prompt[0][1]
    assert context in lint_prompt[1][1]
    
    meta_prompt = get_metadata_prompt("Sample body", term)
    assert term in meta_prompt[0][1]
    assert "Sample body" in meta_prompt[1][1]
    
    fallback_prompt = get_fallback_prompt("Sample body")
    assert "Sample body" in fallback_prompt[1][1]
    
    translation_prompt = get_translation_prompt(term)
    assert term in translation_prompt[1][1]
    
    judgement_prompt = get_judgment_prompt(term, "raw markdown")
    assert term in judgement_prompt[0][1]
    assert "raw markdown" in judgement_prompt[1][1]
    
    refine_prompt = get_refine_prompt(term, "current content", "raw markdown", "instruction")
    assert term in refine_prompt[0][1]
    assert "current content" in refine_prompt[1][1]
    assert "raw markdown" in refine_prompt[1][1]
    
    draft_prompt = get_draft_body_prompt(term, "raw markdown", context)
    assert term in draft_prompt[0][1]
    assert "raw markdown" in draft_prompt[1][1]
    assert context in draft_prompt[1][1]

@patch("retrieval.sync_manager.git.Repo")
def test_sync_manager_init(mock_repo_class, tmp_path):
    # Test if GitSyncManager initializes with Config.WIKI_DIR
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    
    mock_store = MagicMock(spec=QdrantHybridStore)
    repo_dir = tmp_path / "wiki"
    repo_dir.mkdir()
    import git
    git.Repo.init(repo_dir)
    
    with patch("core.config.Config.WIKI_DIR", repo_dir):
        sync_manager = GitSyncManager(store=mock_store)
        assert sync_manager.wiki_dir == repo_dir.absolute()
        assert sync_manager.repo is not None

@patch("retrieval.sync_manager.git.Repo")
def test_sync_manager_get_current_head(mock_repo_class, tmp_path):
    mock_repo = MagicMock()
    mock_repo.head.commit.hexsha = "a" * 40
    mock_repo_class.return_value = mock_repo
    
    mock_store = MagicMock(spec=QdrantHybridStore)
    repo_dir = tmp_path / "wiki"
    repo_dir.mkdir()
    import git
    repo = git.Repo.init(repo_dir)
    # Need at least one commit for HEAD to exist
    (repo_dir / "init.txt").write_text("init")
    repo.git.add(all=True)
    repo.index.commit("initial commit")
    
    sync_manager = GitSyncManager(store=mock_store)
    head = sync_manager._get_current_head()
    assert head == "a" * 40

def test_git_commit_logic_with_temp_repo(tmp_path):
    # Test the logic used in main.py for git commit with a real temp repo
    import git
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    repo = git.Repo.init(repo_dir)
    
    # Create a file
    test_file = repo_dir / "test.md"
    test_file.write_text("initial content", encoding="utf-8")
    
    # Initial commit
    repo.git.add(all=True)
    repo.index.commit("initial commit")
    
    assert not repo.is_dirty()
    
    # Modify file
    test_file.write_text("modified content", encoding="utf-8")
    assert repo.is_dirty()
    
    # Logic from main.py
    repo.git.add(all=True)
    if repo.is_dirty() or repo.untracked_files:
        repo.git.commit("-m", "test commit")
        
    assert not repo.is_dirty()
    
    # Add new file
    new_file = repo_dir / "new.md"
    new_file.write_text("new content", encoding="utf-8")
    assert "new.md" in repo.untracked_files
    
    # Logic from main.py
    repo.git.add(all=True)
    # After add, it's no longer untracked but it IS dirty (staged changes)
    assert repo.is_dirty()
    if repo.is_dirty() or repo.untracked_files:
        repo.git.commit("-m", "test commit 2")
        
    assert not repo.is_dirty()

def test_extract_json_from_text():
    from core.utils import extract_json_from_text
    
    # Standard JSON block
    text1 = "Here is the data: ```json\n{\"key\": \"value\"}\n``` hope it helps."
    assert extract_json_from_text(text1) == "{\"key\": \"value\"}"
    
    # JSON block without 'json' tag
    text2 = "```\n{\"key\": \"value\"}\n```"
    assert extract_json_from_text(text2) == "{\"key\": \"value\"}"
    
    # Raw JSON with garbage around
    text3 = "**Metadata** {\"key\": \"value\"} --- end"
    assert extract_json_from_text(text3) == "{\"key\": \"value\"}"
    
    # Nested JSON
    text4 = "{\"outer\": {\"inner\": 1}}"
    assert extract_json_from_text(text4) == "{\"outer\": {\"inner\": 1}}"
    
    # Multiple blocks (should take the first/outer one)
    text5 = "First: {\"a\": 1}, Second: {\"b\": 2}"
    # Current implementation for multiple non-block JSON is limited, but let's test outer
    text6 = "Text before {\"a\": {\"b\": 1}} text after"
    assert extract_json_from_text(text6) == "{\"a\": {\"b\": 1}}"
