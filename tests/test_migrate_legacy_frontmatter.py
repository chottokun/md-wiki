import pytest
from core.utils import _migrate_legacy_frontmatter

def test_migrate_empty():
    assert _migrate_legacy_frontmatter({}) == {}
    # Passing None should be handled gracefully if possible,
    # but based on the code it might raise TypeError if not guarded.
    # The code has "if not data: return data", and in Python "not None" is True.
    # So _migrate_legacy_frontmatter(None) returns None.
    assert _migrate_legacy_frontmatter(None) is None

def test_migrate_abstract_to_description():
    # abstract -> description
    data = {"abstract": "test abstract"}
    expected = {"description": "test abstract"}
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_summary_to_description():
    # summary -> description
    data = {"summary": "test summary"}
    expected = {"description": "test summary"}
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_abstract_already_has_description():
    # abstract should be removed if description already exists
    data = {"abstract": "old abstract", "description": "new description"}
    expected = {"description": "new description"}
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_summary_already_has_description():
    # summary should be removed if description already exists
    data = {"summary": "old summary", "description": "new description"}
    expected = {"description": "new description"}
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_updated_to_timestamp():
    # updated -> timestamp
    data = {"updated": "2024-01-01"}
    expected = {"timestamp": "2024-01-01"}
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_updated_already_has_timestamp():
    # updated should be removed if timestamp already exists
    data = {"updated": "2023-01-01", "timestamp": "2024-01-01"}
    expected = {"timestamp": "2024-01-01"}
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_type_wiki():
    # type: wiki -> type: Article
    data = {"type": "wiki"}
    expected = {"type": "Article"}
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_type_other():
    # type: concept should NOT be changed
    data = {"type": "Concept"}
    expected = {"type": "Concept"}
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_combinations():
    data = {
        "type": "wiki",
        "abstract": "summary",
        "updated": "2024-01-01",
        "other": "value"
    }
    expected = {
        "type": "Article",
        "description": "summary",
        "timestamp": "2024-01-01",
        "other": "value"
    }
    assert _migrate_legacy_frontmatter(data) == expected

def test_migrate_preserves_unrelated():
    data = {"title": "My Page", "tags": ["tag1"]}
    expected = {"title": "My Page", "tags": ["tag1"]}
    assert _migrate_legacy_frontmatter(data) == expected
