from core.utils import dump_frontmatter
import pytest

def test_dump_frontmatter_basic():
    data = {"title": "Test Page", "tags": ["test", "unit"]}
    result = dump_frontmatter(data)
    assert result.startswith("---\n")
    assert result.endswith("\n---\n")
    assert "title: Test Page" in result
    assert "tags:" in result
    assert "- test" in result
    assert "- unit" in result

def test_dump_frontmatter_empty():
    data = {}
    result = dump_frontmatter(data)
    # ruamel.yaml produces '{}' for an empty dict in some configurations
    assert result == "---\n{}\n---\n" or result == "---\n---\n"

def test_dump_frontmatter_nested():
    data = {"meta": {"author": "Jules", "priority": 1}}
    result = dump_frontmatter(data)
    assert "meta:" in result
    assert "  author: Jules" in result
    assert "  priority: 1" in result

def test_dump_frontmatter_unicode():
    data = {"title": "テストページ", "content": "日本語"}
    result = dump_frontmatter(data)
    assert "title: テストページ" in result
    assert "content: 日本語" in result

def test_dump_frontmatter_special_chars():
    data = {"path": "C:\\Users\\Test", "url": "https://example.com?q=1&b=2"}
    result = dump_frontmatter(data)
    assert "path: C:\\Users\\Test" in result
    assert "url: https://example.com?q=1&b=2" in result

def test_dump_frontmatter_multiline():
    data = {"description": "This is a\nmulti-line\nstring."}
    result = dump_frontmatter(data)
    # ruamel.yaml might use | or just \n
    assert "description:" in result
    assert "multi-line" in result

def test_dump_frontmatter_none():
    data = {"key": None}
    result = dump_frontmatter(data)
    # ruamel.yaml produces 'key:\n' for None in this configuration
    assert "key:" in result
