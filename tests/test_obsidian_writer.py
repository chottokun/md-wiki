import unittest
import shutil
from pathlib import Path
from output.obsidian_writer import ObsidianWriter

class TestObsidianWriter(unittest.TestCase):
    def setUp(self):
        self.test_wiki_dir = Path("tests/test_wiki")
        self.test_staged_dir = Path("tests/test_staged")
        self.writer = ObsidianWriter(
            wiki_dir=str(self.test_wiki_dir),
            staged_dir=str(self.test_staged_dir)
        )

    def tearDown(self):
        shutil.rmtree(self.test_wiki_dir, ignore_errors=True)
        shutil.rmtree(self.test_staged_dir, ignore_errors=True)

    def test_create_and_approve_new_page(self):
        page_name = "NewPage"
        proposed_content = "This is a new page content."
        
        # 1. レビューファイルの作成
        review_path = self.writer.create_review_file(page_name, proposed_content)
        self.assertTrue(review_path.exists())
        
        # 2. 承認
        success = self.writer.approve_update(page_name)
        self.assertTrue(success)
        
        # 3. Wikiへの反映確認
        wiki_path = self.test_wiki_dir / f"{page_name}.md"
        self.assertTrue(wiki_path.exists())
        with open(wiki_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), proposed_content)
            
        # 4. レビューファイルが削除されていること
        self.assertFalse(review_path.exists())

    def test_diff_generation_existing_page(self):
        page_name = "ExistingPage"
        # 既存ファイル作成
        (self.test_wiki_dir / f"{page_name}.md").write_text("Line 1\nLine 2")
        
        proposed_content = "Line 1\nLine 2 modified"
        review_path = self.writer.create_review_file(page_name, proposed_content)
        
        with open(review_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("-Line 2", content)
            self.assertIn("+Line 2 modified", content)

    def test_add_log_entry(self):
        self.writer.add_log_entry("test_action", "This is a test detail")
        log_path = self.test_wiki_dir / "log.md"
        self.assertTrue(log_path.exists())
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("test_action | This is a test detail", content)

    def test_update_index(self):
        # 複数ページ作成
        (self.test_wiki_dir / "PageA.md").write_text("# Page A\nContent with #Tag1", encoding="utf-8")
        (self.test_wiki_dir / "PageB.md").write_text("# Page B\nContent with #Tag1 and #Tag2", encoding="utf-8")
        
        self.writer.update_index()
        
        index_path = self.test_wiki_dir / "Home.md"
        self.assertTrue(index_path.exists())
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("[[PageA]]", content)
            self.assertIn("[[PageB]]", content)
            self.assertIn("### #Tag1", content)
            self.assertIn("### #Tag2", content)

    from unittest.mock import patch
    @patch('subprocess.run')
    def test_get_page_activity(self, mock_run):
        # 擬似的なモック結果
        import subprocess
        class MockCompletedProcess:
            def __init__(self, stdout, returncode=0):
                self.stdout = stdout
                self.returncode = returncode

        # get_page_activityは2回subprocess.runを呼ぶ
        # 1回目: Hot (PageA)
        # 2回目: Stale (PageCが存在しつつ、1ヶ月以内に更新されていない)
        (self.test_wiki_dir / "PageC.md").write_text("Old content", encoding="utf-8")

        mock_run.side_effect = [
            MockCompletedProcess("PageA.md\nPageA.md\nPageB.md\n"), # Hot
            MockCompletedProcess("PageA.md\nPageB.md\n") # Recent
        ]

        activity = self.writer.get_page_activity()
        
        self.assertIn("PageA", activity["hot"])
        self.assertIn("PageC", activity["stale"])

if __name__ == '__main__':
    unittest.main()
