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
    
    # 1. ページA: フロントマターにタグ、本文にタグ、本文にヘッダー（タグと誤認してはいけない）
    content_a = """---
tags: [fm-tag1, fm-tag2]
---
# Header
This is a #body-tag1 and another #body-tag2/sub.
## NotATag
URL: http://example.com/#not-a-tag
Multiple ### hash is not a tag.
#StartingTag at start of line.
"""
    (temp_wiki / "PageA.md").write_text(content_a, encoding="utf-8")
    
    # 2. ページB: タグの重複
    content_b = """---
tags: [duplicate-tag, fm-tag1]
---
# #duplicate-tag (this is a header starting with #)
Another #duplicate-tag.
"""
    (temp_wiki / "PageB.md").write_text(content_b, encoding="utf-8")
    
    writer.update_index()
    
    home_md = (temp_wiki / "Home.md").read_text(encoding="utf-8")
    
    # Verify PageA tags in list (Sorted: StartingTag, body-tag1, body-tag2/sub, fm-tag1, fm-tag2)
    assert "- [[PageA]] #StartingTag #body-tag1 #body-tag2/sub #fm-tag1 #fm-tag2" in home_md
    
    # Verify PageB tags in list (deduplicated and sorted)
    assert "- [[PageB]] #duplicate-tag #fm-tag1" in home_md
    
    # Verify Tag Index
    assert "## 🏷️ タグ別インデックス" in home_md
    assert "- #body-tag1 : [[PageA]]" in home_md
    assert "- #fm-tag1 : [[PageA]], [[PageB]]" in home_md
    assert "- #duplicate-tag : [[PageB]]" in home_md
    
    # Ensure Header "Header" is not a tag
    assert "#Header" not in home_md
    assert "#NotATag" not in home_md
    assert "#not-a-tag" not in home_md # from URL
