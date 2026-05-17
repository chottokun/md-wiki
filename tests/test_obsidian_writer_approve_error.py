import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import shutil
from output.obsidian_writer import ObsidianWriter

class TestObsidianWriterApproveError(unittest.TestCase):
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
        """wiki_path.write_text が失敗した場合に False を返し、エラーをログに記録することを検証。"""
        page_name = "ErrorPage"
        content = "## Proposed Full Content\nError content\n---\n"

        # レビューファイルの作成
        review_file = self.test_staged_dir / "errorpage_review.md"
        review_file.write_text(content, encoding="utf-8")

        # Path.write_text をモックして例外を投げさせる
        with patch.object(Path, "write_text", side_effect=Exception("Disk full")):
            with self.assertLogs("output.obsidian_writer", level="ERROR") as cm:
                success = self.writer.approve_update(page_name)
                self.assertFalse(success)
                self.assertTrue(any("Wikiの更新反映中にエラーが発生しました: Disk full" in output for output in cm.output))

        # レビューファイルが削除されずに残っていることを確認
        self.assertTrue(review_file.exists())

    def test_approve_update_unlink_error(self):
        """staged_path.unlink が失敗した場合に False を返し、エラーをログに記録することを検証。"""
        page_name = "UnlinkErrorPage"
        content = "## Proposed Full Content\nUnlink error content\n---\n"

        # レビューファイルの作成
        review_file = self.test_staged_dir / "unlinkerrorpage_review.md"
        review_file.write_text(content, encoding="utf-8")

        # Path.unlink をモックして例外を投げさせる
        with patch.object(Path, "unlink", side_effect=Exception("Permission denied")):
            with self.assertLogs("output.obsidian_writer", level="ERROR") as cm:
                success = self.writer.approve_update(page_name)
                self.assertFalse(success)
                self.assertTrue(any("Wikiの更新反映中にエラーが発生しました: Permission denied" in output for output in cm.output))

        # Wikiファイル自体は書き込まれているが、unlink失敗で全体としてFalseになる
        wiki_file = self.test_wiki_dir / "unlinkerrorpage.md"
        self.assertTrue(wiki_file.exists())
        self.assertTrue(review_file.exists())

    def test_approve_update_missing_staged_file(self):
        """レビューファイルが存在しない場合に False を返し、エラーをログに記録することを検証。"""
        page_name = "NonExistentPage"

        with self.assertLogs("output.obsidian_writer", level="ERROR") as cm:
            success = self.writer.approve_update(page_name)
            self.assertFalse(success)
            self.assertTrue(any("承認対象のファイルが見つかりません" in output for output in cm.output))

if __name__ == '__main__':
    unittest.main()
