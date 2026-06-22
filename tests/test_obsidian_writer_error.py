import unittest
from unittest.mock import MagicMock, patch
import shutil
from pathlib import Path
from output.obsidian_writer import ObsidianWriter

class TestObsidianWriterErrorHandling(unittest.TestCase):
    def setUp(self):
        self.test_wiki_dir = Path("tests/error_test_wiki")
        self.test_staged_dir = Path("tests/error_test_staged")
        self.writer = ObsidianWriter(
            wiki_dir=str(self.test_wiki_dir),
            staged_dir=str(self.test_staged_dir)
        )
        self.test_wiki_dir.mkdir(parents=True, exist_ok=True)
        self.test_staged_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_wiki_dir, ignore_errors=True)
        shutil.rmtree(self.test_staged_dir, ignore_errors=True)

    def test_approve_update_write_error(self):
        """Test that approve_update returns False and logs error when writing fails."""
        page_name = "ErrorPage"
        review_file = self.test_staged_dir / f"{page_name}_review.md"
        review_file.write_text("Some content", encoding="utf-8")

        with patch.object(Path, 'write_text') as mock_write:
            mock_write.side_effect = Exception("Write failed")

            with self.assertLogs('output.obsidian_writer', level='ERROR') as cm:
                success = self.writer.approve_update(page_name)
                self.assertFalse(success)
                self.assertTrue(any("Write failed" in output for output in cm.output))

        self.assertTrue(review_file.exists())

    def test_approve_update_unlink_error(self):
        """Test that approve_update returns False and logs error when unlinking fails."""
        page_name = "UnlinkErrorPage"
        review_file = self.test_staged_dir / f"{page_name}_review.md"
        review_file.write_text("Some content", encoding="utf-8")

        with patch.object(Path, 'unlink') as mock_unlink:
            mock_unlink.side_effect = Exception("Unlink failed")

            with self.assertLogs('output.obsidian_writer', level='ERROR') as cm:
                success = self.writer.approve_update(page_name)
                self.assertFalse(success)
                self.assertTrue(any("Unlink failed" in output for output in cm.output))

        wiki_file = self.test_wiki_dir / f"{page_name}.md"
        self.assertTrue(wiki_file.exists())

if __name__ == '__main__':
    unittest.main()
