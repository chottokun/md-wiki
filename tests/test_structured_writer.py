import pytest
from pathlib import Path
from output.obsidian_writer import ObsidianWriter
from core.schemas import WikiPageSchema

def test_create_draft_from_schema(tmp_path):
    """Pydanticスキーマから正しくWikiが生成されるかテストする。"""
    # 一時的なWikiディレクトリを設定
    writer = ObsidianWriter(wiki_dir=tmp_path)
    
    data = {
        "title": "TDDによる開発",
        "abstract": "テスト駆動開発の有効性について。",
        "concepts": ["Red-Green-Refactor", "自動テスト", "設計品質"],
        "body": "本文には [[リンク]] が含まれるべきです。",
        "tags": ["TDD", "Python"],
        "aliases": ["Test Driven Development"]
    }
    
    # スキーマ検証
    schema = WikiPageSchema(**data)
    
    # 実行
    wiki_path = writer.create_draft_from_schema(schema.dict())
    
    # 検証
    content = wiki_path.read_text(encoding="utf-8")
    
    # 1. YAMLフロントマターの存在
    assert "---" in content
    assert "type: wiki" in content
    assert "TDD" in content
    assert "Test Driven Development" in content
    
    # 2. 構造の正しさ
    assert "# TDDによる開発" in content
    assert "> [!abstract] 要約" in content
    assert "## 主要な概念" in content
    assert "- Red-Green-Refactor" in content
    assert "本文には [[リンク]] が含まれるべきです。" in content
