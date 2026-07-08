import pytest
import os
import shutil
from pathlib import Path
from core.git_utils import run_git_commit
from core.config import Config
from retrieval.sync_manager import GitSyncManager
from unittest.mock import MagicMock
import git

@pytest.fixture
def temp_wiki_repo(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    repo = git.Repo.init(wiki_dir)
    repo.config_writer().set_value("user", "name", "Security Tester").release()
    repo.config_writer().set_value("user", "email", "security@example.com").release()

    # Initial commit to have HEAD
    init_file = wiki_dir / "init.md"
    init_file.write_text("initial")
    repo.git.add(all=True)
    repo.index.commit("initial commit")

    old_wiki_dir = Config.WIKI_DIR
    Config.WIKI_DIR = wiki_dir
    yield wiki_dir, repo
    Config.WIKI_DIR = old_wiki_dir

def test_run_git_commit_injection_mitigation(temp_wiki_repo):
    wiki_dir, repo = temp_wiki_repo

    # Message that looks like an option
    injection_message = "--help"

    # Modify a file
    (wiki_dir / "init.md").write_text("changed")

    # Should commit literally and NOT trigger help (which might raise or just not commit)
    run_git_commit(injection_message)

    # Verify the last commit message is literally "--help"
    last_msg = repo.git.log("-1", "--format=%s")
    assert last_msg == injection_message

def test_run_git_commit_dash_v_mitigation(temp_wiki_repo):
    wiki_dir, repo = temp_wiki_repo

    injection_message = "-v"
    (wiki_dir / "init.md").write_text("changed again")

    run_git_commit(injection_message)

    last_msg = repo.git.log("-1", "--format=%s")
    assert last_msg == injection_message

def test_sync_manager_diff_injection_mitigation(temp_wiki_repo):
    wiki_dir, repo = temp_wiki_repo

    # File name that looks like an option
    dangerous_file = "-v"
    full_path = wiki_dir / dangerous_file
    full_path.write_text("some content")

    repo.git.add(all=True)
    repo.index.commit("add dangerous file")

    # Modify it
    full_path.write_text("modified content")

    sync_manager = GitSyncManager(store=MagicMock(), wiki_dir=wiki_dir)
    # This calls repo.git.diff('HEAD', '--', file_path)
    diff = sync_manager.get_unstaged_diff(dangerous_file)

    assert "modified content" in diff
    # If it failed to treat '-v' as a path, diff would likely be empty or an error

def test_sync_manager_path_traversal_mitigation(temp_wiki_repo, tmp_path):
    wiki_dir, repo = temp_wiki_repo

    # Create a secret file outside the wiki directory
    secret_file = tmp_path / "secret_outside.txt"
    secret_file.write_text("secret content")

    sync_manager = GitSyncManager(store=MagicMock(), wiki_dir=wiki_dir)

    # Mock repo.untracked_files to include a traversal path
    with MagicMock() as mock_repo:
        sync_manager.repo = mock_repo
        mock_repo.git.diff.return_value = "" # No diff in git

        # Test relative traversal
        relative_traversal = "../secret_outside.txt"
        mock_repo.untracked_files = [relative_traversal]
        assert sync_manager.get_unstaged_diff(relative_traversal) == ""

        # Test absolute traversal
        absolute_traversal = str(secret_file.absolute())
        mock_repo.untracked_files = [absolute_traversal]
        assert sync_manager.get_unstaged_diff(absolute_traversal) == ""
