import unittest
import os
import shutil
from pathlib import Path
from output.obsidian_writer import ObsidianWriter
from core.utils import normalize_term

class TestUIBackend(unittest.TestCase):
    def setUp(self):
        self.test_wiki_dir = Path("tests/ui_test_wiki")
        self.test_staged_dir = Path("tests/ui_test_staged")
        self.writer = ObsidianWriter(
            wiki_dir=str(self.test_wiki_dir),
            staged_dir=str(self.test_staged_dir)
        )
        self.test_wiki_dir.mkdir(parents=True, exist_ok=True)
        self.test_staged_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_wiki_dir, ignore_errors=True)
        shutil.rmtree(self.test_staged_dir, ignore_errors=True)

    def test_ui_approve_flow(self):
        """UIから承認ボタンが押された時の流れをテスト。"""
        page_name = "UITestPage"
        safe_name = normalize_term(page_name)
        content = "## Proposed Full Content\nNew content from UI review\n---\n## Agent Metadata (Do not delete)"
        
        # 1. レビューファイルの作成
        review_file = self.test_staged_dir / f"{safe_name}_review.md"
        review_file.write_text(content, encoding="utf-8")
        
        # 2. UI上の承認アクションをシミュレート
        success = self.writer.approve_update(page_name)
        self.assertTrue(success)
        
        # 3. 反映の確認
        wiki_file = self.test_wiki_dir / f"{safe_name}.md"
        self.assertTrue(wiki_file.exists())
        self.assertEqual(wiki_file.read_text(encoding="utf-8"), "New content from UI review")
        self.assertFalse(review_file.exists())

if __name__ == '__main__':
    unittest.main()
