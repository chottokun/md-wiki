import pytest
from core.schemas import WikiFrontmatterSchema
from output.obsidian_writer import ObsidianWriter
import os
import shutil

def test_frontmatter_schema_normalization():
    # 1. 正常系: リストが正しく保持されるか
    data = {
        "tags": ["RAG", "LLM"],
        "aliases": ["Self-RAG"],
        "abstract": "Test summary"
    }
    fm = WikiFrontmatterSchema.model_validate(data)
    assert fm.tags == ["RAG", "LLM"]
    assert fm.aliases == ["Self-RAG"]
    assert fm.type == "Concept"

    # 2. 異常系・補正: 文字列が渡されてもリストに変換されるか（Pydanticの基本機能）
    # ※ Pydantic v2 のデフォルトでは List[str] に str は自動変換されないため、
    # 以前の ObsidianWriter の手動補正ロジックが正しく機能するか確認
    
    writer = ObsidianWriter(wiki_dir="test_wiki")
    raw_data = {
        "tags": "SingleTag",
        "aliases": "SingleAlias",
    }
    # ObsidianWriter._prepare_metadata 経由でテスト
    prepared = writer._prepare_metadata(raw_data, None, None)
    
    assert isinstance(prepared["tags"], list)
    assert "SingleTag" in prepared["tags"]
    assert "未審査" in prepared["tags"]
    assert isinstance(prepared["aliases"], list)
    assert "SingleAlias" in prepared["aliases"]

def test_frontmatter_deduplication():
    writer = ObsidianWriter(wiki_dir="test_wiki")
    raw_data = {
        "tags": ["RAG", "RAG", "LLM"],
        "aliases": ["SELF-RAG", "self-rag", "SELF-RAG"]
    }
    prepared = writer._prepare_metadata(raw_data, None, None)
    
    # 重複排除とソートの確認
    assert prepared["tags"] == ["LLM", "RAG", "未審査"]
    assert prepared["aliases"] == ["SELF-RAG", "self-rag"]

if __name__ == "__main__":
    # 簡易実行
    try:
        test_frontmatter_schema_normalization()
        test_frontmatter_deduplication()
        print("✅ Metadata Logic Tests Passed!")
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        exit(1)
