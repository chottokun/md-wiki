import pytest
from pathlib import Path
from core.utils import normalize_term, parse_frontmatter, dump_frontmatter, extract_json_from_text
from output.obsidian_writer import ObsidianWriter
from core.schemas import DraftConfig

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

def test_parse_frontmatter_invalid_yaml():
    """不正なYAMLが含まれる場合に(None, content)が返ることを確認する"""
    invalid_content = "---\n[invalid yaml\n---\nBody content"
    data, body = parse_frontmatter(invalid_content)
    assert data is None
    assert body == invalid_content

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
    path = writer.create_draft_file(DraftConfig(page_name="New Topic", proposed_content=content))
    
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
    writer.create_draft_file(DraftConfig(page_name="merge_test", proposed_content=first))
    
    # 2回目（別のsourcesで上書き）
    second = "---\nsources: [\"source_b\"]\n---\n# Page A Updated"
    path = writer.create_draft_file(DraftConfig(page_name="merge_test", proposed_content=second))
    
    data, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    # 両方のソースが残っていること
    assert "source_a" in data["sources"]
    assert "source_b" in data["sources"]

def test_extract_json_none_and_empty():
    """Verify that None or empty strings return None."""
    assert extract_json_from_text(None) is None
    assert extract_json_from_text("") is None

def test_extract_json_no_braces():
    """Verify that text without braces returns None."""
    assert extract_json_from_text("plain text") is None
    assert extract_json_from_text("JSON is missing here") is None

def test_extract_json_single_brace():
    """Verify that single braces return None."""
    assert extract_json_from_text("{") is None
    assert extract_json_from_text("}") is None
    assert extract_json_from_text("text with { but no end") is None
    assert extract_json_from_text("text with } but no start") is None

def test_extract_json_reversed_braces():
    """Verify that braces in reversed order return None."""
    assert extract_json_from_text("}{") is None
    assert extract_json_from_text("Closing } then opening {") is None

def test_extract_json_unbalanced_braces():
    """Verify that unbalanced braces return None."""
    assert extract_json_from_text("{{}") is None
    assert extract_json_from_text("{}}") is None
    assert extract_json_from_text("{\"a\": 1") is None
    assert extract_json_from_text("{\"a\": 1}}") is None

def test_extract_json_empty_braces():
    """Verify that empty braces are correctly extracted."""
    assert extract_json_from_text("{}") == "{}"
    assert extract_json_from_text("Result: {}") == "{}"

def test_extract_json_valid_but_malformed_json():
    """
    Verify that the function only checks for brace matching, not JSON validity.
    (This is the responsibility of the caller or a dedicated JSON parser)
    """
    assert extract_json_from_text("{\"a\": }") == "{\"a\": }"
