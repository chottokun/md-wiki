import pytest
from pathlib import Path
from migrate_to_okf import migrate_frontmatter_and_content
from core.utils import parse_frontmatter

@pytest.fixture
def wiki_root(tmp_path):
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "concepts").mkdir()
    (root / "sources").mkdir()
    (root / "raw_markdown").mkdir()
    (root / "references").mkdir()
    return root

def test_migrate_basic_renames(wiki_root):
    file_path = wiki_root / "test.md"
    content = """---
abstract: "This is a summary of more than ten characters"
updated: "2023-10-27 10:30"
---
# Test Page
Content here."""
    file_path.write_text(content, encoding="utf-8")

    migrate_frontmatter_and_content(file_path, wiki_root, dry_run=False)

    new_content = file_path.read_text(encoding="utf-8")
    data, body = parse_frontmatter(new_content)

    assert "abstract" not in data
    assert data["description"] == "This is a summary of more than ten characters"
    assert "updated" not in data
    assert data["timestamp"] == "2023-10-27T10:30:00+09:00"
    assert data["type"] == "Article"

def test_migrate_type_inference(wiki_root):
    # Concept
    concept_file = wiki_root / "concepts" / "concept.md"
    concept_file.write_text("# Concept", encoding="utf-8")
    migrate_frontmatter_and_content(concept_file, wiki_root, dry_run=False)
    data, _ = parse_frontmatter(concept_file.read_text(encoding="utf-8"))
    assert data["type"] == "Concept"

    # Source
    source_file = wiki_root / "sources" / "src.md"
    source_file.write_text("# Source", encoding="utf-8")
    migrate_frontmatter_and_content(source_file, wiki_root, dry_run=False)
    data, _ = parse_frontmatter(source_file.read_text(encoding="utf-8"))
    assert data["type"] == "Source"

def test_migrate_title_extraction(wiki_root):
    # From H1
    file_path = wiki_root / "page.md"
    file_path.write_text("# Real Title\nBody", encoding="utf-8")
    migrate_frontmatter_and_content(file_path, wiki_root, dry_run=False)
    data, _ = parse_frontmatter(file_path.read_text(encoding="utf-8"))
    assert data["title"] == "Real Title"

    # From filename
    file_path2 = wiki_root / "filename_title.md"
    file_path2.write_text("No H1 here", encoding="utf-8")
    migrate_frontmatter_and_content(file_path2, wiki_root, dry_run=False)
    data, _ = parse_frontmatter(file_path2.read_text(encoding="utf-8"))
    assert data["title"] == "filename_title"

def test_migrate_citation_section(wiki_root):
    file_path = wiki_root / "citations.md"
    content = """# Page
Body text.

## 🔗 関連リンク
- [Link](http://example.com)
- [[Internal Link]]

More body text?"""
    file_path.write_text(content, encoding="utf-8")

    migrate_frontmatter_and_content(file_path, wiki_root, dry_run=False)

    new_content = file_path.read_text(encoding="utf-8")
    assert "## 🔗 関連リンク" not in new_content
    assert "# Citations" in new_content
    assert "- [Link](http://example.com)" in new_content
    assert "- [[Internal Link]]" in new_content

    # Logic in code: body = body.rstrip(); body += f"\n\n# Citations\n{links_content}"
    # If there was "More body text?" after the section, it was kept in `body` but the citation section was removed.
    # citation_section_pattern removes the section.
    assert "More body text?" in new_content

def test_migrate_dry_run(wiki_root):
    file_path = wiki_root / "dry_run.md"
    content = "# Dry Run\nOld content"
    file_path.write_text(content, encoding="utf-8")

    migrate_frontmatter_and_content(file_path, wiki_root, dry_run=True)

    assert file_path.read_text(encoding="utf-8") == content

def test_migrate_no_frontmatter(wiki_root):
    file_path = wiki_root / "no_fm.md"
    content = "# No Frontmatter\nJust body"
    file_path.write_text(content, encoding="utf-8")

    migrate_frontmatter_and_content(file_path, wiki_root, dry_run=False)

    new_content = file_path.read_text(encoding="utf-8")
    assert new_content.startswith("---")
    data, body = parse_frontmatter(new_content)
    assert data["type"] == "Article"
    assert data["title"] == "No Frontmatter"

def test_migrate_iso_date_handling(wiki_root):
    file_path = wiki_root / "dates.md"
    content = """---
updated: "2023-10-27"
created: "2023-01-01 12:00"
---
# Dates"""
    file_path.write_text(content, encoding="utf-8")

    migrate_frontmatter_and_content(file_path, wiki_root, dry_run=False)

    data, _ = parse_frontmatter(file_path.read_text(encoding="utf-8"))
    assert data["timestamp"] == "2023-10-27T00:00:00+09:00"
    assert data["created"] == "2023-01-01T12:00:00+09:00"
