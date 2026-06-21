import unittest
import os
import shutil
import tempfile
from pathlib import Path
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

if __name__ == "__main__":
    unittest.main()
