import pytest
import sys
from core.utils import normalize_term, dump_frontmatter, parse_frontmatter
from output.obsidian_writer import ObsidianWriter

def test_unicode_normalization_and_encoding():
    """Windows/CP932環境で問題になりやすい文字の正規化とエンコーディングをテストする。"""
    
    # 1. 様々なハイフン・ダッシュ類
    # \u2010 (HYPHEN), \u2013 (EN DASH), \u2014 (EM DASH), \uFF0D (FULLWIDTH HYPHEN-MINUS)
    hyphen_cases = ["self-rag", "self\u2010rag", "self\u2013rag", "self\u2014rag", "self\uFF0Drag"]
    for case in hyphen_cases:
        assert normalize_term(case) == "self-rag"
    
    # 2. 全角英数とスペース
    assert normalize_term("ＬＬＭ　モデル") == "llm_モデル"
    
    # 3. 絵文字や特殊記号（CP932でエラーになるもの）
    # ✨, 🚀, 🔗 など
    special_text = "✨ 成果物 🚀"
    norm_text = normalize_term(special_text)
    assert "成果物" in norm_text
    
    # 4. YAMLフロントマターのエンコーディング
    data = {
        "title": "絵文字テスト ✨",
        "tags": ["タグ１", "🚀-rocket"],
        "content": "Windowsのハイフン―テスト"
    }
    yaml_str = dump_frontmatter(data)
    
    # UTF-8でデコードできるか
    assert "絵文字テスト ✨" in yaml_str
    
    # パースし直して整合性を確認
    parsed_data, _ = parse_frontmatter(yaml_str)
    assert parsed_data["title"] == "絵文字テスト ✨"
    assert "🚀-rocket" in parsed_data["tags"]

def test_obsidian_writer_encoding_robustness(tmp_path):
    """実際にファイルに書き込んでエンコーディングエラーが出ないかテストする。"""
    writer = ObsidianWriter(wiki_dir=tmp_path)
    
    # CP932で表現不可能な文字を含むデータ
    data = {
        "title": "Unicode文字の試練",
        "abstract": "この抽象には ✨ 🚀 🔗 が含まれます。",
        "concepts": ["ハイフン—", "ダッシュ–"],
        "body": "本文には特殊な記号が含まれます：\n- 🔀 クロスリンク\n- 📝 メモ",
        "tags": ["検証", "🧪"],
        "aliases": ["Unicode-Test"]
    }
    
    # 実行 (エラーが出ないことを確認)
    try:
        wiki_path = writer.create_draft_from_schema(data)
        content = wiki_path.read_text(encoding="utf-8")
        assert "✨ 🚀 🔗" in content
        assert "🧪" in content
    except UnicodeEncodeError as e:
        pytest.fail(f"UnicodeEncodeError occurred on Windows: {e}")
