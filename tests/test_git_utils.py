import sys
from unittest.mock import MagicMock, patch
import pytest
from pathlib import Path

# Mock dependencies that might be missing or trigger heavy imports
sys.modules["dotenv"] = MagicMock()
sys.modules["git"] = MagicMock()

from core.git_utils import run_git_commit
from core.config import Config

class TestRunGitCommit:
    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_successful_commit(self, mock_logger, mock_repo_class, tmp_path):
        # Setup
        Config.WIKI_DIR = tmp_path
        mock_repo = mock_repo_class.return_value
        mock_repo.is_dirty.return_value = True
        mock_repo.untracked_files = []

        # Execute
        run_git_commit("Test message")

        # Verify
        mock_repo.git.add.assert_called_once_with(all=True)
        mock_repo.git.commit.assert_called_once_with("-m", "Test message")

    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_no_changes_no_commit(self, mock_logger, mock_repo_class, tmp_path):
        # Setup
        Config.WIKI_DIR = tmp_path
        mock_repo = mock_repo_class.return_value
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = []

        # Execute
        run_git_commit("Test message")

        # Verify
        mock_repo.git.add.assert_called_once_with(all=True)
        mock_repo.git.commit.assert_not_called()

    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_untracked_files_trigger_commit(self, mock_logger, mock_repo_class, tmp_path):
        # Setup
        Config.WIKI_DIR = tmp_path
        mock_repo = mock_repo_class.return_value
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = ["new_file.md"]

        # Execute
        run_git_commit("Test message")

        # Verify
        mock_repo.git.commit.assert_called_once_with("-m", "Test message")

    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_stale_lock_file_removal(self, mock_logger, mock_repo_class, tmp_path):
        # Setup
        wiki_dir = tmp_path
        Config.WIKI_DIR = wiki_dir
        git_dir = wiki_dir / ".git"
        git_dir.mkdir()
        lock_file = git_dir / "index.lock"
        lock_file.write_text("lock")

        mock_repo = mock_repo_class.return_value
        mock_repo.is_dirty.return_value = True

        # Execute
        run_git_commit("Test message")

        # Verify
        assert not lock_file.exists()
        mock_logger.warning.assert_called_once()
        assert "Removing stale git lock file" in mock_logger.warning.call_args[0][0]

    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_error_handling(self, mock_logger, mock_repo_class, tmp_path):
        # Setup
        Config.WIKI_DIR = tmp_path
        mock_repo_class.side_effect = Exception("Git error")

        # Execute
        run_git_commit("Test message")

        # Verify
        mock_logger.error.assert_called_once()
        assert "Wikiへの自動コミットに失敗しました" in mock_logger.error.call_args[0][0]
