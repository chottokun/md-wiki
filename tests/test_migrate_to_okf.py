import unittest
import os
import shutil
import tempfile
import io
from pathlib import Path
from unittest.mock import patch
from migrate_to_okf import migrate_frontmatter_and_content
from core.utils import parse_frontmatter

class TestMigrateToOKF(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.wiki_root = self.test_dir / "wiki"
        self.wiki_root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_type_inference_concept(self):
        concept_dir = self.wiki_root / "concepts"
        concept_dir.mkdir()
        file_path = concept_dir / "test.md"
        file_path.write_text("---\ntitle: Test\n---\nBody", encoding="utf-8")

        migrate_frontmatter_and_content(file_path, self.wiki_root, dry_run=False)

        data, body = parse_frontmatter(file_path.read_text(encoding="utf-8"))
        self.assertEqual(data["type"], "Concept")
        self.assertEqual(data["title"], "Test")

    def test_field_renames_and_dates(self):
        file_path = self.wiki_root / "article.md"
        content = """---
abstract: "This is a summary."
updated: "2023-10-27 10:00"
created: "2023-10-20"
---
# Article Title
Body
"""
        file_path.write_text(content, encoding="utf-8")

        migrate_frontmatter_and_content(file_path, self.wiki_root, dry_run=False)

        data, body = parse_frontmatter(file_path.read_text(encoding="utf-8"))
        self.assertEqual(data["description"], "This is a summary.")
        self.assertNotIn("abstract", data)
        # We fixed the bug, so now it SHOULD be in ISO format.
        self.assertEqual(data["timestamp"], "2023-10-27T10:00:00+09:00")
        self.assertEqual(data["created"], "2023-10-20T00:00:00+09:00")
        self.assertEqual(data["title"], "Article Title")

    def test_title_from_filename(self):
        file_path = self.wiki_root / "NoTitle.md"
        file_path.write_text("---\ntype: Article\n---\nNo H1 here", encoding="utf-8")

        migrate_frontmatter_and_content(file_path, self.wiki_root, dry_run=False)

        data, body = parse_frontmatter(file_path.read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "NoTitle")

    def test_citations_migration(self):
        file_path = self.wiki_root / "citations.md"
        content = """---
title: Citations Test
---
Intro.

## 🔗 関連リンク
* [Link 1](https://example.com)
* [Link 2](https://example.org)

More content?
"""
        file_path.write_text(content, encoding="utf-8")

        migrate_frontmatter_and_content(file_path, self.wiki_root, dry_run=False)

        final_content = file_path.read_text(encoding="utf-8")
        self.assertIn("# Citations", final_content)
        self.assertIn("* [Link 1](https://example.com)", final_content)
        self.assertNotIn("## 🔗 関連リンク", final_content)
        self.assertIn("* [Link 2](https://example.org)", final_content)

    def test_dry_run(self):
        file_path = self.wiki_root / "dry_run.md"
        content = "---\nabstract: Summary\n---\nBody"
        file_path.write_text(content, encoding="utf-8")

        migrate_frontmatter_and_content(file_path, self.wiki_root, dry_run=True)

        self.assertEqual(file_path.read_text(encoding="utf-8"), content)

    def test_no_frontmatter(self):
        file_path = self.wiki_root / "no_fm.md"
        content = "# No Frontmatter\nJust body"
        file_path.write_text(content, encoding="utf-8")

        migrate_frontmatter_and_content(file_path, self.wiki_root, dry_run=False)

        new_content = file_path.read_text(encoding="utf-8")
        self.assertTrue(new_content.startswith("---"))
        data, body = parse_frontmatter(new_content)
        self.assertEqual(data["type"], "Article")
        self.assertEqual(data["title"], "No Frontmatter")

    def test_iso_date_handling(self):
        file_path = self.wiki_root / "dates.md"
        content = """---
updated: "2023-10-27"
created: "2023-01-01 12:00"
---
# Dates"""
        file_path.write_text(content, encoding="utf-8")

        migrate_frontmatter_and_content(file_path, self.wiki_root, dry_run=False)

        data, _ = parse_frontmatter(file_path.read_text(encoding="utf-8"))
        self.assertEqual(data["timestamp"], "2023-10-27T00:00:00+09:00")
        self.assertEqual(data["created"], "2023-01-01T12:00:00+09:00")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_migrate_frontmatter_and_content_read_error(self, mock_stdout):
        """
        Test that migrate_frontmatter_and_content handles file read errors gracefully.
        """
        file_path = Path("non_existent_file.md")
        wiki_root = Path(".")

        # Mock Path.read_text to raise an exception
        with patch.object(Path, "read_text", side_effect=Exception("Read error")):
            migrate_frontmatter_and_content(file_path, wiki_root, dry_run=False)

        # Verify that the error message was printed
        self.assertIn("❌ Error reading non_existent_file.md: Read error", mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_migrate_frontmatter_and_content_write_error(self, mock_stdout):
        """
        Test that migrate_frontmatter_and_content handles file write errors gracefully.
        """
        file_path = Path("existent_file.md")
        wiki_root = Path(".")

        # Mock Path.read_text to return some content
        # Mock Path.write_text to raise an exception
        with patch.object(Path, "read_text", return_value="---\ntype: Article\n---\nBody content\n"), \
             patch.object(Path, "write_text", side_effect=Exception("Write error")):
            migrate_frontmatter_and_content(file_path, wiki_root, dry_run=False)

        # Verify that the write error message was printed
        self.assertIn("❌ Error writing existent_file.md: Write error", mock_stdout.getvalue())

if __name__ == "__main__":
    unittest.main()
