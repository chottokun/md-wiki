import pytest
from pathlib import Path
from output.obsidian_writer import ObsidianWriter
import shutil
import os

@pytest.fixture
def temp_wiki(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    return wiki_dir

def test_tag_extraction_and_indexing(temp_wiki):
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))
    
    content_a = """---
type: Article
tags: [fm-tag1, fm-tag2]
description: Page A description
---
# Page A
This is Page A content.
"""
    (temp_wiki / "PageA.md").write_text(content_a, encoding="utf-8")
    
    content_b = """---
type: Article
tags: [duplicate-tag, fm-tag1]
description: Page B description
---
# Page B
Another Page B content.
"""
    (temp_wiki / "PageB.md").write_text(content_b, encoding="utf-8")
    
    writer.update_index()
    
    index_md = (temp_wiki / "index.md").read_text(encoding="utf-8")
    
    # Verify PageA and PageB standard markdown links are present
    assert "[PageA](PageA.md)" in index_md
    assert "Page A description" in index_md
    assert "[PageB](PageB.md)" in index_md
    assert "Page B description" in index_md
