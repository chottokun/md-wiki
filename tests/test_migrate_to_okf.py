import pytest
from pathlib import Path
from unittest.mock import patch
from migrate_to_okf import migrate_frontmatter_and_content

def test_migrate_frontmatter_and_content_read_error(capsys):
    """
    Test that migrate_frontmatter_and_content handles file read errors gracefully.
    """
    file_path = Path("non_existent_file.md")
    wiki_root = Path(".")

    # Mock Path.read_text to raise an exception
    with patch.object(Path, "read_text", side_effect=Exception("Read error")):
        migrate_frontmatter_and_content(file_path, wiki_root, dry_run=False)

    # Capture the output
    captured = capsys.readouterr()

    # Verify that the error message was printed
    assert "❌ Error reading non_existent_file.md: Read error" in captured.out

def test_migrate_frontmatter_and_content_write_error(capsys):
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

    # Capture the output
    captured = capsys.readouterr()

    # Verify that the write error message was printed
    assert "❌ Error writing existent_file.md: Write error" in captured.out

