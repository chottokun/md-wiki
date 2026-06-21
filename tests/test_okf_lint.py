import pytest
from pathlib import Path
from okf_lint import lint_wiki

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
