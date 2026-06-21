from __future__ import annotations
import pytest
from pathlib import Path
from okf_lint import lint_wiki

# --- Tests from PR 64 ---

def test_lint_wiki_missing_dir(capsys):
    assert lint_wiki("non_existent_dir") is False
    captured = capsys.readouterr()
    assert "Wiki directory does not exist" in captured.out

def test_lint_wiki_valid_concept(tmp_path, capsys):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    concept_file = wiki_dir / "concept.md"
    concept_file.write_text("---\ntype: concept\ndescription: test\ntimestamp: 2023-10-27\n---\nBody", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is True
    captured = capsys.readouterr()
    assert "1/1 documents have valid frontmatter" in captured.out
    assert "Result: CONFORMANT" in captured.out

def test_lint_wiki_invalid_concept(tmp_path, capsys):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    # Missing frontmatter
    f1 = wiki_dir / "no_fm.md"
    f1.write_text("No frontmatter here", encoding="utf-8")

    # Missing type
    f2 = wiki_dir / "no_type.md"
    f2.write_text("---\ndescription: test\ntimestamp: 2023-10-27\n---\nBody", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is False
    captured = capsys.readouterr()
    assert "Missing or invalid YAML frontmatter" in captured.out
    assert "Required 'type' field is missing or empty" in captured.out
    assert "Result: NON-CONFORMANT" in captured.out

def test_lint_wiki_warnings(tmp_path, capsys):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    # Missing description and timestamp
    f1 = wiki_dir / "warnings.md"
    f1.write_text("---\ntype: concept\n---\nBody", encoding="utf-8")

    # Should still be conformant despite warnings
    assert lint_wiki(str(wiki_dir)) is True
    captured = capsys.readouterr()
    assert "Missing recommended 'description' field" in captured.out
    assert "Missing recommended 'timestamp' field" in captured.out
    assert "Result: CONFORMANT" in captured.out

def test_lint_wiki_index_md(tmp_path, capsys):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    # Valid index.md
    index_file = wiki_dir / "index.md"
    index_file.write_text("# Index", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is True

    # Invalid index.md (with frontmatter)
    index_file.write_text("---\ntitle: Index\n---\n# Index", encoding="utf-8")
    assert lint_wiki(str(wiki_dir)) is False
    captured = capsys.readouterr()
    assert "index.md should NOT contain YAML frontmatter" in captured.out

def test_lint_wiki_log_md(tmp_path, capsys):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    log_file = wiki_dir / "log.md"

    # Valid log.md
    log_file.write_text("# Log\n\n## 2023-10-27\n- update", encoding="utf-8")
    assert lint_wiki(str(wiki_dir)) is True

    # Invalid log.md (no H1)
    log_file.write_text("## 2023-10-27\n- update", encoding="utf-8")
    assert lint_wiki(str(wiki_dir)) is False
    captured = capsys.readouterr()
    assert "log.md: Must start with a top-level H1 header" in captured.out

    # log.md warning (no date headers)
    log_file.write_text("# Log\nJust some text", encoding="utf-8")
    # It should still be conformant if only warning
    assert lint_wiki(str(wiki_dir)) is True
    captured = capsys.readouterr()
    assert "No YYYY-MM-DD date headers found" in captured.out


# --- Tests from PR 68 ---

def test_lint_wiki_non_existent_dir(tmp_path):
    """Scenario 1: Returns False when given a path that doesn't exist."""
    non_existent = tmp_path / "missing_wiki"
    assert lint_wiki(str(non_existent)) is False

def test_lint_wiki_minimal_conformant(tmp_path):
    """Scenario 2: Returns True for a wiki with a single valid concept document."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    doc = wiki_dir / "concept.md"
    doc.write_text("---\ntype: concept\ndescription: A test concept\ntimestamp: 2024-01-01\n---\n# Concept Content", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is True

def test_lint_wiki_missing_frontmatter(tmp_path):
    """Scenario 3: Returns False when a concept document is missing YAML frontmatter."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    doc = wiki_dir / "no_fm.md"
    doc.write_text("# Just Content", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is False

def test_lint_wiki_missing_type(tmp_path):
    """Scenario 4: Returns False when a concept document's frontmatter is missing the required 'type' field."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    doc = wiki_dir / "no_type.md"
    doc.write_text("---\ndescription: Missing type\ntimestamp: 2024-01-01\n---\n# Content", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is False

def test_lint_wiki_missing_recommended_fields(tmp_path):
    """Scenario 5: Returns True (but generates warnings) when recommended fields like 'description' or 'timestamp' are missing."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    doc = wiki_dir / "missing_rec.md"
    # Missing description and timestamp
    doc.write_text("---\ntype: concept\n---\n# Content", encoding="utf-8")

    # Missing log.md date headers (by having a log.md without them)
    log_file = wiki_dir / "log.md"
    log_file.write_text("# Log\nNo date headers here.", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is True

def test_lint_wiki_index_invalid(tmp_path):
    """Scenario 6: Returns False if an index.md file contains YAML frontmatter."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    # Valid concept doc
    doc = wiki_dir / "concept.md"
    doc.write_text("---\ntype: concept\n---\n# Content", encoding="utf-8")

    # Invalid index.md
    index_file = wiki_dir / "index.md"
    index_file.write_text("---\ntitle: Index\n---\n# Welcome", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is False

def test_lint_wiki_log_invalid_header(tmp_path):
    """Scenario 7: Returns False if log.md does not start with a top-level H1 header."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    # Valid concept doc
    doc = wiki_dir / "concept.md"
    doc.write_text("---\ntype: concept\n---\n# Content", encoding="utf-8")

    # Invalid log.md (starts with H2)
    log_file = wiki_dir / "log.md"
    log_file.write_text("## Log Start\n", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is False

def test_lint_wiki_log_missing_dates(tmp_path):
    """Scenario 8: Returns True (but generates warnings) if log.md lacks YYYY-MM-DD date headers."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    # Valid concept doc
    doc = wiki_dir / "concept.md"
    doc.write_text("---\ntype: concept\n---\n# Content", encoding="utf-8")

    # log.md with H1 but no YYYY-MM-DD headers
    log_file = wiki_dir / "log.md"
    log_file.write_text("# Log\n## Not a date\n", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is True

def test_lint_wiki_full_conformant(tmp_path):
    """Scenario 9: Returns True for a wiki structure containing all required and recommended elements."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    # Conformant concept doc
    doc = wiki_dir / "concept.md"
    doc.write_text("---\ntype: concept\ndescription: Perfect\ntimestamp: 2024-01-01\n---\n# Content", encoding="utf-8")

    # Conformant index.md
    index_file = wiki_dir / "index.md"
    index_file.write_text("# Index\nWelcome to the wiki.", encoding="utf-8")

    # Conformant log.md
    log_file = wiki_dir / "log.md"
    log_file.write_text("# Log\n## 2024-01-01\nInitial entry.", encoding="utf-8")

    assert lint_wiki(str(wiki_dir)) is True
