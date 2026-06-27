import unittest
import os
import shutil
import tempfile
import io
import argparse
from pathlib import Path
from unittest.mock import patch
from migrate_to_okf import (
    migrate_frontmatter_and_content,
    backup_wiki,
    _infer_type,
    _format_iso_datetime,
    migrate_log_file,
    main
)
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

    @patch('shutil.make_archive')
    def test_backup_wiki(self, mock_make_archive):
        # Case 1: Directory exists
        backup_wiki(self.wiki_root)
        mock_make_archive.assert_called_once()
        args, kwargs = mock_make_archive.call_args
        self.assertTrue(args[0].startswith("wiki_backup_"))
        self.assertEqual(args[1], 'zip')
        self.assertEqual(args[2], self.wiki_root)

        # Case 2: Directory does not exist
        mock_make_archive.reset_mock()
        backup_wiki(Path("non_existent_dir"))
        mock_make_archive.assert_not_called()

    def test_infer_type(self):
        # concepts
        file_path = self.wiki_root / "concepts" / "test.md"
        self.assertEqual(_infer_type(file_path, self.wiki_root, None), "Concept")

        # raw_markdown
        file_path = self.wiki_root / "raw_markdown" / "test.md"
        self.assertEqual(_infer_type(file_path, self.wiki_root, None), "RawSource")

        # references
        file_path = self.wiki_root / "references" / "test.md"
        self.assertEqual(_infer_type(file_path, self.wiki_root, None), "Reference")

        # sources
        file_path = self.wiki_root / "sources" / "test.md"
        self.assertEqual(_infer_type(file_path, self.wiki_root, None), "Source")

        # default (Article)
        file_path = self.wiki_root / "test.md"
        self.assertEqual(_infer_type(file_path, self.wiki_root, None), "Article")

        # preserved type
        file_path = self.wiki_root / "concepts" / "test.md"
        self.assertEqual(_infer_type(file_path, self.wiki_root, "CustomType"), "CustomType")

        # overwrite generic type
        self.assertEqual(_infer_type(file_path, self.wiki_root, "wiki"), "Concept")

    def test_format_iso_datetime(self):
        # YYYY-MM-DD HH:mm
        self.assertEqual(_format_iso_datetime("2023-10-27 10:00"), "2023-10-27T10:00:00+09:00")

        # YYYY-MM-DD
        self.assertEqual(_format_iso_datetime("2023-10-27"), "2023-10-27T00:00:00+09:00")

        # Already ISO (or invalid for the custom parser, should return as is)
        self.assertEqual(_format_iso_datetime("2023-10-27T10:00:00+09:00"), "2023-10-27T10:00:00+09:00")
        self.assertEqual(_format_iso_datetime("Not a date"), "Not a date")

        # Non-string input
        self.assertEqual(_format_iso_datetime(12345), "12345")

    def test_migrate_log_file(self):
        log_path = self.wiki_root / "log.md"
        content = """# Old Log
## [2023-10-27 10:00] create | [[Test Page]]
## [2023-10-27 11:00] update | Modified content
## 2023-10-26
* Existing entry
"""
        log_path.write_text(content, encoding="utf-8")

        migrate_log_file(log_path, dry_run=False)

        new_content = log_path.read_text(encoding="utf-8")
        self.assertIn("# Directory Update Log", new_content)
        self.assertIn("## 2023-10-27", new_content)
        self.assertIn("* **Create**: [Test Page](Test Page.md).", new_content)
        self.assertIn("* **Update**: Modified content.", new_content)
        self.assertIn("## 2023-10-26", new_content)
        self.assertIn("* Existing entry", new_content)

    @patch('output.obsidian_writer.ObsidianWriter')
    @patch('migrate_to_okf.setup_argparse')
    def test_main(self, mock_setup_argparse, mock_obsidian_writer):
        # Mock arguments
        mock_setup_argparse.return_value = argparse.Namespace(
            wiki_dir=str(self.wiki_root),
            dry_run=False,
            backup=False
        )

        # Setup files
        home_md = self.wiki_root / "Home.md"
        home_md.write_text("# Home", encoding="utf-8")

        article_md = self.wiki_root / "article.md"
        article_md.write_text("# Article", encoding="utf-8")

        # Mock ObsidianWriter
        mock_writer_instance = mock_obsidian_writer.return_value

        main()

        # Check Home.md renamed to index.md
        self.assertFalse(home_md.exists())
        self.assertTrue((self.wiki_root / "index.md").exists())

        # Check article migrated
        article_content = article_md.read_text(encoding="utf-8")
        self.assertIn("type: Article", article_content)

        # Check ObsidianWriter called
        mock_obsidian_writer.assert_called_once_with(wiki_dir=str(self.wiki_root))
        mock_writer_instance.update_index.assert_called_once()

if __name__ == "__main__":
    unittest.main()
