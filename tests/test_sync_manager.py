import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil
from retrieval.sync_manager import GitSyncManager
from langchain_core.documents import Document

class TestGitSyncManager(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.wiki_dir = Path(self.temp_dir.name).absolute()

        # Mock git.Repo
        with patch("retrieval.sync_manager.git.Repo") as mock_repo_class:
            self.mock_repo = MagicMock()
            mock_repo_class.return_value = self.mock_repo
            self.sync_manager = GitSyncManager(store=self.mock_store, wiki_dir=self.wiki_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_changed_files(self):
        """Test file identification and filtering logic in get_changed_files."""
        # 1. Create real files in temp wiki
        (self.wiki_dir / "new.md").write_text("content")
        (self.wiki_dir / "changed.md").write_text("content")
        (self.wiki_dir / "hidden").mkdir()
        (self.wiki_dir / "hidden" / ".secret.md").write_text("content")
        (self.wiki_dir / "image.png").write_text("data")
        (self.wiki_dir / "Home.md").write_text("home")
        (self.wiki_dir / "log.md").write_text("log")

        # 2. Mock repo state (relative paths)
        self.mock_repo.untracked_files = ["new.md", "image.png", "Home.md"]

        diff1 = MagicMock()
        diff1.b_path = "changed.md"
        diff2 = MagicMock()
        diff2.b_path = "log.md"

        self.mock_repo.index.diff.side_effect = [
            [diff1], # diff(None)
            []       # diff('HEAD')
        ]

        # Mock _get_last_synced_hash
        with patch.object(GitSyncManager, "_get_last_synced_hash", return_value="abc1234"):
            # Mock repo.commit().diff()
            diff3 = MagicMock()
            diff3.b_path = "hidden/.secret.md"
            self.mock_repo.commit.return_value.diff.return_value = [diff3]

            changed = self.sync_manager.get_changed_files()

            # Expected: new.md, changed.md, hidden/.secret.md
            # Filtered: image.png (suffix), Home.md (name), log.md (name)

            expected_paths = {
                self.wiki_dir / "new.md",
                self.wiki_dir / "changed.md",
                self.wiki_dir / "hidden/.secret.md"
            }
            # Convert to absolute for comparison
            expected_paths = {p.absolute() for p in expected_paths}
            self.assertEqual(changed, expected_paths)

    def test_perform_incremental_sync_full(self):
        """Test fallback to full sync when no state exists."""
        with patch.object(GitSyncManager, "_get_last_synced_hash", return_value=""), \
             patch.object(GitSyncManager, "_get_current_head", return_value="newhead123"), \
             patch.object(GitSyncManager, "_save_sync_state") as mock_save:

            self.sync_manager.perform_incremental_sync(include_unreviewed=True)

            self.mock_store.sync_from_disk.assert_called_once_with(include_unreviewed=True)
            mock_save.assert_called_once_with("newhead123")

    def test_perform_incremental_sync_incremental(self):
        """Test incremental sync with file updates."""
        test_file = self.wiki_dir / "test_page.md"
        test_file.write_text("Some content")

        with patch.object(GitSyncManager, "_get_last_synced_hash", return_value="oldhead"), \
             patch.object(GitSyncManager, "get_changed_files", return_value={test_file}), \
             patch.object(GitSyncManager, "_get_current_head", return_value="newhead"), \
             patch.object(GitSyncManager, "_save_sync_state") as mock_save:

            dummy_docs = [Document(page_content="chunk1", metadata={"source": "test_page"})]
            self.mock_store.get_chunks.return_value = dummy_docs

            # Setup config
            from core.config import Config
            with patch.object(Config, "INCREMENTAL_SYNC_BATCH_SIZE", 100), \
                 patch.object(Config, "INCLUDE_UNREVIEWED", True):

                self.sync_manager.perform_incremental_sync()

            # Verify deletion of old source
            self.mock_store.delete_sources.assert_called_once_with(["test_page"])
            # Verify addition of new docs
            self.mock_store.add_documents.assert_called_once_with(dummy_docs)
            # Verify state saved
            mock_save.assert_called_once_with("newhead")

    def test_perform_incremental_sync_unreviewed_skip(self):
        """Test that unreviewed files are skipped when include_unreviewed=False."""
        file_clean = self.wiki_dir / "clean.md"
        file_clean.write_text("Normal content")
        file_unreviewed = self.wiki_dir / "unreviewed.md"
        file_unreviewed.write_text("Content with #未審査 tag")

        with patch.object(GitSyncManager, "_get_last_synced_hash", return_value="oldhead"), \
             patch.object(GitSyncManager, "get_changed_files", return_value={file_clean, file_unreviewed}), \
             patch.object(GitSyncManager, "_get_current_head", return_value="newhead"), \
             patch.object(GitSyncManager, "_save_sync_state"):

            self.mock_store.get_chunks.side_effect = lambda content, meta: [Document(page_content=content, metadata=meta)]

            self.sync_manager.perform_incremental_sync(include_unreviewed=False)

            all_deleted = []
            for call in self.mock_store.delete_sources.call_args_list:
                all_deleted.extend(call.args[0])

            self.assertIn("clean", all_deleted)
            self.assertNotIn("unreviewed", all_deleted)

            all_added_docs = []
            for call in self.mock_store.add_documents.call_args_list:
                all_added_docs.extend(call.args[0])

            # Only clean.md should have its document added
            self.assertEqual(len(all_added_docs), 1)
            self.assertEqual(all_added_docs[0].metadata["source"], "clean")

    def test_perform_incremental_sync_raw_markdown(self):
        """Test metadata generation for raw markdown files."""
        raw_dir = self.wiki_dir / "raw_markdown"
        raw_dir.mkdir()
        raw_file = raw_dir / "source_raw.md"
        raw_file.write_text("Raw content")

        with patch.object(GitSyncManager, "_get_last_synced_hash", return_value="oldhead"), \
             patch.object(GitSyncManager, "get_changed_files", return_value={raw_file}), \
             patch.object(GitSyncManager, "_get_current_head", return_value="newhead"), \
             patch.object(GitSyncManager, "_save_sync_state"):

            self.sync_manager.perform_incremental_sync(include_unreviewed=True)

            # Check metadata passed to get_chunks
            self.mock_store.get_chunks.assert_called_once()
            args, _ = self.mock_store.get_chunks.call_args
            _, metadata = args

            self.assertEqual(metadata["source"], "source.pdf")
            self.assertEqual(metadata["type"], "raw_source")

    def test_get_unstaged_diff(self):
        """Test get_unstaged_diff for both HEAD diff and untracked files."""
        # Case 1: HEAD diff exists
        self.mock_repo.git.diff.return_value = "diff content"
        res = self.sync_manager.get_unstaged_diff("test.md")
        self.assertEqual(res, "diff content")

        # Case 2: Untracked file
        self.mock_repo.git.diff.return_value = ""
        self.mock_repo.untracked_files = ["new.md"]
        new_file = self.wiki_dir / "new.md"
        new_file.write_text("file content")

        res = self.sync_manager.get_unstaged_diff("new.md")
        self.assertEqual(res, "file content")

if __name__ == "__main__":
    unittest.main()
