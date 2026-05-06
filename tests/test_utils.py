import pytest
from pathlib import Path
from core.utils import normalize_term, parse_frontmatter, dump_frontmatter
from output.obsidian_writer import ObsidianWriter

@pytest.fixture
def temp_wiki(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    return wiki_dir

def test_normalize_term():
    # スペースとアンダースコアの統一
    assert normalize_term("Machine Learning") == "machine_learning"
    assert normalize_term("Machine_Learning") == "machine_learning"
    assert normalize_term("Machine  Learning") == "machine_learning"
    
    # Unicode正規化と小文字化
    assert normalize_term("ＬＬＭ") == "llm"
    assert normalize_term("ＲＬＨＦ") == "rlhf"
    
    # 特殊なハイフンの統一
    assert normalize_term("Retrieval‑Augmented") == "retrieval-augmented"
    assert normalize_term("Self-RAG") == "self-rag"
    
    # 括弧の統一
    assert normalize_term("LLM（大規模言語モデル）") == "llm(大規模言語モデル)"
    
    # 前後の空白
    assert normalize_term("  RAG  ") == "rag"

def test_normalize_term_colon():
    """コロン入りのMediaWiki記法が安全に正規化される"""
    assert normalize_term("Category:LLM") == "categoryllm"
    assert ":" not in normalize_term("Category:LLM")

def test_normalize_term_md_extension():
    """.md拡張子が除去される"""
    assert normalize_term("page_name.md") == "page_name"
    assert normalize_term("Self-RAG.md") == "self-rag"

def test_yaml_frontmatter_parsing():
    content = """---
tags: [test, wiki]
aliases: ["AI", "Bot"]
---
# Main Content
Body text here."""
    
    data, body = parse_frontmatter(content)
    assert data["tags"] == ["test", "wiki"]
    assert data["aliases"] == ["AI", "Bot"]
    assert body == "# Main Content\nBody text here."

def test_yaml_frontmatter_dump():
    data = {
        "tags": ["alpha", "beta"],
        "updated": "2024-01-01"
    }
    dumped = dump_frontmatter(data)
    assert "tags:" in dumped
    assert "alpha" in dumped
    assert "updated:" in dumped
    assert dumped.startswith("---")
    assert dumped.strip().endswith("---")

def test_new_file_has_no_diff(temp_wiki):
    """新規作成ファイルにDiffブロックが混入しない"""
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))
    content = "# Brand New Page\n\nSome content here."
    path = writer.create_draft_file("New Topic", content)
    
    text = path.read_text(encoding="utf-8")
    assert "> [!info]" not in text
    assert "```diff" not in text
    assert "+++" not in text
    # ---はYAMLデリミタとしてのみ許可
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "---":
            # YAMLの開始/終了 or フッターの区切り線のみ許可
            continue
        assert "---" not in line or line.startswith("- "), f"Unexpected --- at line {i}: {line}"

def test_update_preserves_sources(temp_wiki):
    """更新時にsourcesが消えない"""
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))
    
    # 初回作成（sourcesつきのYAML）
    first = "---\nsources: [\"source_a\"]\n---\n# Page A"
    writer.create_draft_file("merge_test", first)
    
    # 2回目（別のsourcesで上書き）
    second = "---\nsources: [\"source_b\"]\n---\n# Page A Updated"
    path = writer.create_draft_file("merge_test", second)
    
    data, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    # 両方のソースが残っていること
    assert "source_a" in data["sources"]
    assert "source_b" in data["sources"]
