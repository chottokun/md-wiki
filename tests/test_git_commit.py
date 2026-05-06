import sys
from unittest.mock import MagicMock, patch

# Mocking dependencies that might be missing or cause side effects during import
mock_git = MagicMock()
mock_agent_graph = MagicMock()
mock_langgraph = MagicMock()
mock_core_llm_router = MagicMock()
mock_retrieval_query_engine = MagicMock()
mock_output_obsidian_writer = MagicMock()
mock_retrieval_sync_manager = MagicMock()
mock_dotenv = MagicMock()

sys.modules["git"] = mock_git
sys.modules["agent.graph"] = mock_agent_graph
sys.modules["langgraph"] = mock_langgraph
sys.modules["langgraph.types"] = MagicMock()
sys.modules["core.llm_router"] = mock_core_llm_router
sys.modules["retrieval.query_engine"] = mock_retrieval_query_engine
sys.modules["output.obsidian_writer"] = mock_output_obsidian_writer
sys.modules["retrieval.sync_manager"] = mock_retrieval_sync_manager
sys.modules["dotenv"] = mock_dotenv

# Now we can import run_git_commit from main
# We need to make sure main.py can be imported without issues
with patch("main.qdrant_store", MagicMock()), \
     patch("main.app", MagicMock()):
    from main import run_git_commit
from core.config import Config

import pytest
from pathlib import Path

def test_run_git_commit_success(tmp_path):
    """
    Test successful commit when repo is dirty.
    """
    # Setup Config.WIKI_DIR to a temp directory
    with patch.object(Config, "WIKI_DIR", tmp_path):
        mock_repo_instance = mock_git.Repo.return_value
        mock_repo_instance.is_dirty.return_value = True
        mock_repo_instance.untracked_files = []

        run_git_commit("test message")

        mock_git.Repo.assert_called_once_with(tmp_path)
        mock_repo_instance.git.add.assert_called_once_with(all=True)
        mock_repo_instance.git.commit.assert_called_once_with("-m", "test message")

def test_run_git_commit_no_changes(tmp_path):
    """
    Test that commit is not called when there are no changes.
    """
    with patch.object(Config, "WIKI_DIR", tmp_path):
        mock_repo_instance = mock_git.Repo.return_value
        mock_repo_instance.is_dirty.return_value = False
        mock_repo_instance.untracked_files = []

        # Reset mocks
        mock_git.Repo.reset_mock()
        mock_repo_instance.git.add.reset_mock()
        mock_repo_instance.git.commit.reset_mock()

        run_git_commit("test message")

        mock_repo_instance.git.add.assert_called_once_with(all=True)
        mock_repo_instance.git.commit.assert_not_called()

def test_run_git_commit_untracked_files(tmp_path):
    """
    Test successful commit when there are untracked files.
    """
    with patch.object(Config, "WIKI_DIR", tmp_path):
        mock_repo_instance = mock_git.Repo.return_value
        mock_repo_instance.is_dirty.return_value = False
        mock_repo_instance.untracked_files = ["new_file.md"]

        # Reset mocks
        mock_repo_instance.git.commit.reset_mock()

        run_git_commit("test message")

        mock_repo_instance.git.commit.assert_called_once_with("-m", "test message")

def test_run_git_commit_removes_stale_lock(tmp_path):
    """
    Test that stale git lock file is removed.
    """
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)
    lock_file = git_dir / "index.lock"
    lock_file.write_text("lock")

    with patch.object(Config, "WIKI_DIR", tmp_path):
        mock_repo_instance = mock_git.Repo.return_value
        mock_repo_instance.is_dirty.return_value = True

        run_git_commit("test message")

        assert not lock_file.exists()

def test_run_git_commit_exception_handling(tmp_path):
    """
    Test that exceptions are caught and logged.
    """
    with patch.object(Config, "WIKI_DIR", tmp_path):
        mock_git.Repo.side_effect = Exception("Git Error")

        # This should not raise an exception
        with patch("main.logger") as mock_logger:
            run_git_commit("test message")
            mock_logger.error.assert_called()
            # The message is in Japanese in the code
            args, kwargs = mock_logger.error.call_args
            assert "Wikiへの自動コミットに失敗しました" in args[0]
