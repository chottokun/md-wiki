import pytest
from pathlib import Path
import shutil
from output.obsidian_writer import ObsidianWriter
from core.schemas import DraftConfig
from core.utils import parse_frontmatter

@pytest.fixture
def temp_wiki(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    return wiki_dir

def test_create_draft_new_file(temp_wiki):
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))
    page_name = "Test Page"
    content = "# Hello World"
    
    path = writer.create_draft_file(DraftConfig(page_name=page_name, proposed_content=content))
    
    assert path.exists()
    assert path.name == "test_page.md"
    
    data, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert "未審査" in data["tags"]
    assert "created" in data
    assert "# Hello World" in body

def test_create_draft_update_existing(temp_wiki):
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))
    page_name = "Update Test"
    
    # 1回目：新規作成
    writer.create_draft_file(DraftConfig(page_name=page_name, proposed_content="---\ntags: [old]\n---\nOld Content"))
    
    # 2回目：更新
    new_content = "# New Content"
    path = writer.create_draft_file(DraftConfig(page_name=page_name, proposed_content=new_content))
    
    full_text = path.read_text(encoding="utf-8")
    data, body = parse_frontmatter(full_text)
    
    # タグが維持されつつ「未審査」が追加されているか
    assert "old" in data["tags"]
    assert "未審査" in data["tags"]
    
    # 差分セクションが含まれているか
    assert "> [!info] AIからの更新提案" in full_text
    assert "Old Content" in full_text # 差分の中にあるはず
    assert "# New Content" in body

def test_initialization_flow(temp_wiki):
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))
    writer.update_index()
    
    home_path = temp_wiki / "Home.md"
    assert home_path.exists()
    assert "# 🏠 RAG-Wiki Home" in home_path.read_text(encoding="utf-8")
