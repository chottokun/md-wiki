import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from retrieval.sync_manager import GitSyncManager

class TestGetUnstagedDiff(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.wiki_dir = Path("/mock/wiki")

        with patch("retrieval.sync_manager.git.Repo") as mock_repo_class:
            self.mock_repo = MagicMock()
            mock_repo_class.return_value = self.mock_repo
            self.sync_manager = GitSyncManager(store=self.mock_store, wiki_dir=self.wiki_dir)

    def test_diff_exists(self):
        """1. HEADとの差分がある場合、その差分を返す"""
        expected_diff = "diff --git a/file.md b/file.md\n+new line"
        self.mock_repo.git.diff.return_value = expected_diff

        result = self.sync_manager.get_unstaged_diff("file.md")

        self.assertEqual(result, expected_diff)
        self.mock_repo.git.diff.assert_called_once_with('HEAD', '--', "file.md")

    def test_untracked_file_exists(self):
        """2. 差分がなく、新規ファイル（Untracked）として存在する場合、ファイル内容を返す"""
        self.mock_repo.git.diff.return_value = ""
        self.mock_repo.untracked_files = ["untracked.md"]
        file_content = "new file content"

        # We need to mock Path objects within the sync_manager instance or use a more broad patch
        # Patching Path.exists and Path.read_text globally for this test
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=file_content):
            result = self.sync_manager.get_unstaged_diff("untracked.md")

        self.assertEqual(result, file_content)

    def test_untracked_file_not_exists(self):
        """3. Untrackedだがファイルがディスク上に存在しない場合、空文字を返す"""
        self.mock_repo.git.diff.return_value = ""
        self.mock_repo.untracked_files = ["missing.md"]

        with patch("pathlib.Path.exists", return_value=False):
            result = self.sync_manager.get_unstaged_diff("missing.md")

        self.assertEqual(result, "")

    def test_no_diff_no_untracked(self):
        """4. 差分もなく、Untrackedでもない場合、空文字を返す"""
        self.mock_repo.git.diff.return_value = "  " # whitespace only
        self.mock_repo.untracked_files = []

        result = self.sync_manager.get_unstaged_diff("unchanged.md")

        self.assertEqual(result, "")

    @patch("retrieval.sync_manager.logger")
    def test_exception_handling(self, mock_logger):
        """5. 例外が発生した場合、エラーログを出力し、空文字を返す"""
        self.mock_repo.git.diff.side_effect = Exception("Git error")

        result = self.sync_manager.get_unstaged_diff("error.md")

        self.assertEqual(result, "")
        mock_logger.error.assert_called_once()
        self.assertIn("Git error", mock_logger.error.call_args[0][0])

if __name__ == "__main__":
    unittest.main()
