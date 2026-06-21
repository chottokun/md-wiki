from cleanup_wiki import clean_file_content

def test_clean_file_content_no_markers():
    """Verify no changes are made if markers are absent."""
    content = "---\ntitle: Test\n---\n# Test\nSome content."
    cleaned, changed = clean_file_content(content, "Test", "Test")
    assert not changed
    assert cleaned == content

def test_clean_file_content_invalid_format():
    """Verify no changes if the content doesn't have at least two --- delimiters."""
    content = "# Test\nSome content."
    cleaned, changed = clean_file_content(content, "Test", "Test")
    assert not changed
    assert cleaned == content

def test_clean_file_content_basic_cleaning_title_match():
    """Verify that content is cleaned when an H1 header matches the provided title."""
    content = """---
title: My Page
---
> [!info] AIからの更新提案
```diff
- Old
+ New
```
# My Page
This is the clean content."""

    cleaned, changed = clean_file_content(content, "My Page", "my_page")
    assert changed
    assert "# My Page" in cleaned
    assert "> [!info]" not in cleaned
    assert "```diff" not in cleaned
    assert "This is the clean content." in cleaned
    assert cleaned.startswith("---")
    assert "title: My Page" in cleaned

def test_clean_file_content_title_normalization():
    """Test matching with variations in case, underscores, and dashes."""
    content = """---
title: My-Page
---
```diff
- Old
+ New
```
# My_Page
Cleaned."""

    # Matches because of normalization in clean_file_content
    cleaned, changed = clean_file_content(content, "My-Page", "My-Page")
    assert changed
    assert "# My_Page" in cleaned

def test_clean_file_content_partial_title_match():
    """Verify matching when search_title is a substring of line_title or vice-versa."""
    content = """---
title: My Page Extra
---
```diff
+ Added
```
# My Page
Cleaned."""

    cleaned, changed = clean_file_content(content, "My Page Extra", "my_page_extra")
    assert changed
    assert "# My Page" in cleaned

def test_clean_file_content_fallback_cleaning():
    """Verify that the first H1 header is used if no exact title match is found."""
    content = """---
title: Non-Matching Title
---
```diff
+ Added
```
# Some Other Header
Cleaned content."""

    cleaned, changed = clean_file_content(content, "Non-Matching Title", "non_matching_title")
    assert changed
    assert "# Some Other Header" in cleaned

def test_clean_file_content_exclusion_of_citations():
    """Ensure the fallback ignores # Citations."""
    content = """---
title: Test
---
```diff
+ Added
```
# Citations
Should be ignored.
# Actual Header
Cleaned."""

    cleaned, changed = clean_file_content(content, "Non-existent", "non_existent")
    assert changed
    assert "# Actual Header" in cleaned
    assert "# Citations" not in cleaned # Because it starts from # Actual Header

def test_clean_file_content_rebuild_integrity():
    """Verify that the frontmatter is preserved in the cleaned content."""
    content = """---
author: Jules
tags: [test]
---
```diff
+ Added
```
# Header
Body."""

    cleaned, changed = clean_file_content(content, "Header", "Header")
    assert changed
    assert "author: Jules" in cleaned
    assert "tags: [test]" in cleaned
    assert "---" in cleaned

def test_clean_file_content_no_h1_found():
    """Verify no changes if diff markers are present but no H1 header is found."""
    content = """---
title: Test
---
```diff
+ Added
```
Only text, no H1."""
    cleaned, changed = clean_file_content(content, "Test", "test")
    assert not changed
    assert cleaned == content
