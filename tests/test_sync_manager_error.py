import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from retrieval.sync_manager import GitSyncManager

class TestGitSyncManagerError(unittest.TestCase):
    @patch("retrieval.sync_manager.git.Repo")
    @patch("retrieval.sync_manager.logger")
    def test_get_changed_files_error_path(self, mock_logger, mock_repo_class):
        # Setup
        mock_repo_inst = MagicMock()
        mock_repo_class.return_value = mock_repo_inst

        # Mock index.diff to raise an Exception
        mock_repo_inst.index.diff.side_effect = Exception("Git diff failed")

        mock_store = MagicMock()
        sync_manager = GitSyncManager(store=mock_store, wiki_dir=Path("/tmp/fake_wiki"))

        # Execute
        changed_files = sync_manager.get_changed_files()

        # Verify
        self.assertEqual(changed_files, set())
        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        self.assertIn("Error getting changed files via GitPython", error_msg)
        self.assertIn("Git diff failed", error_msg)

if __name__ == "__main__":
    unittest.main()
