import unittest
from unittest.mock import patch
from pathlib import Path
from output.obsidian_writer import ObsidianWriter

class TestObsidianWriterIndexError(unittest.TestCase):
    def setUp(self):
        self.wiki_dir = Path("test_wiki_index")
        self.wiki_dir.mkdir(exist_ok=True)
        (self.wiki_dir / "page1.md").write_text("---\ntags: [tag1]\n---\nContent 1", encoding="utf-8")
        (self.wiki_dir / "page2.md").write_text("---\ntags: [tag2]\n---\nContent 2", encoding="utf-8")
        (self.wiki_dir / "bad_page.md").write_text("Bad Content", encoding="utf-8")

    def tearDown(self):
        import shutil
        if self.wiki_dir.exists():
            shutil.rmtree(self.wiki_dir)

    def test_update_index_with_read_error(self):
        writer = ObsidianWriter(wiki_dir=str(self.wiki_dir))
        original_read_text = Path.read_text

        def mocked_read_text(path_obj, *args, **kwargs):
            if "bad_page.md" in str(path_obj):
                raise PermissionError("Access denied")
            return original_read_text(path_obj, *args, **kwargs)

        with patch.object(Path, 'read_text', autospec=True, side_effect=mocked_read_text):
            writer.update_index()

        home_path = self.wiki_dir / "Home.md"
        self.assertTrue(home_path.exists())
        content = home_path.read_text(encoding="utf-8")

        # Verify page1 and page2 are present
        self.assertIn("[[page1]]", content)
        self.assertIn("[[page2]]", content)
        # Verify bad_page is skipped
        self.assertNotIn("[[bad_page]]", content)

        # Verify tags
        self.assertIn("#tag1 : [[page1]]", content)
        self.assertIn("#tag2 : [[page2]]", content)

if __name__ == "__main__":
    unittest.main()
