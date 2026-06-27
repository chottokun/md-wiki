import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from core.git_utils import run_git_commit
from core.config import Config

class TestRunGitCommit(unittest.TestCase):
    def setUp(self):
        self.old_wiki_dir = Config.WIKI_DIR

    def tearDown(self):
        Config.WIKI_DIR = self.old_wiki_dir

    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_successful_commit(self, mock_logger, mock_repo_class):
        # Setup
        test_dir = Path("tests/test_git_repo")
        Config.WIKI_DIR = test_dir
        mock_repo = mock_repo_class.return_value
        mock_repo.is_dirty.return_value = True
        mock_repo.untracked_files = []

        # Execute
        run_git_commit("Test message")

        # Verify
        mock_repo.git.add.assert_called_once_with(all=True)
        mock_repo.git.commit.assert_called_once_with("--message=Test message", "--")
        mock_logger.info.assert_called_with("Git Commit: Test message")

    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_no_changes_no_commit(self, mock_logger, mock_repo_class):
        # Setup
        Config.WIKI_DIR = Path("tests/test_git_repo")
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
    def test_untracked_files_trigger_commit(self, mock_logger, mock_repo_class):
        # Setup
        Config.WIKI_DIR = Path("tests/test_git_repo")
        mock_repo = mock_repo_class.return_value
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = ["new_file.md"]

        # Execute
        run_git_commit("Test message")

        # Verify
        mock_repo.git.commit.assert_called_once_with("--message=Test message", "--")

    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_stale_lock_file_removal(self, mock_logger, mock_repo_class):
        # Setup
        wiki_dir = Path("tests/test_git_repo_lock")
        Config.WIKI_DIR = wiki_dir
        git_dir = wiki_dir / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        lock_file = git_dir / "index.lock"
        lock_file.write_text("lock", encoding="utf-8")

        mock_repo = mock_repo_class.return_value
        mock_repo.is_dirty.return_value = True

        # Execute
        run_git_commit("Test message")

        # Verify
        assert not lock_file.exists()
        mock_logger.warning.assert_called_once()
        assert "Removing stale git lock file" in mock_logger.warning.call_args[0][0]
        
        # Cleanup
        import shutil
        shutil.rmtree(wiki_dir)

    @patch("core.git_utils.git.Repo")
    @patch("core.git_utils.logger")
    def test_error_handling(self, mock_logger, mock_repo_class):
        # Setup
        Config.WIKI_DIR = Path("tests/test_git_repo")
        mock_repo_class.side_effect = Exception("Git error")

        # Execute
        run_git_commit("Test message")

        # Verify
        mock_logger.error.assert_called_once()
        assert "Wikiへの自動コミットに失敗しました" in mock_logger.error.call_args[0][0]

if __name__ == "__main__":
    unittest.main()
