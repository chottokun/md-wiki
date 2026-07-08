import pytest
from core.utils import parse_frontmatter

def test_unsafe_yaml_loading():
    """
    Verify that potentially unsafe YAML tags are not processed.
    In typ='safe' mode, ruamel.yaml should raise a ConstructorError or similar when
    encountering tags like !!python/object/apply.
    """
    unsafe_content = """---
title: "Unsafe Page"
malicious: !!python/object/apply:os.system ["echo exploited"]
---
Body text
"""
    # parse_frontmatter catches all exceptions and returns (None, content)
    data, body = parse_frontmatter(unsafe_content)

    # It should fail to parse the frontmatter safely
    assert data is None
    assert "malicious: !!python/object/apply:os.system" in body

def test_safe_yaml_loading():
    """
    Verify that standard YAML frontmatter is still parsed correctly.
    """
    safe_content = """---
title: "Safe Page"
tags: [security, fix]
---
Body text
"""
    data, body = parse_frontmatter(safe_content)

    assert data is not None
    assert data["title"] == "Safe Page"
    assert "security" in data["tags"]
    assert body == "Body text"
