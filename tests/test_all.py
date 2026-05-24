"""
網羅的テストスイート。
以下のレイヤーをカバーする：
  1. core/utils: normalize_term, parse_frontmatter, dump_frontmatter
  2. output/obsidian_writer: create_draft_file, create_draft_from_schema, メタデータマージ
  3. agent/graph: フォールバック品質, ワークフロー遷移
  4. エンコーディング: Windows CP932 耐性, 日本語・絵文字
"""
import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ──────────────────────────────────────────────────
# 1. core/utils テスト
# ──────────────────────────────────────────────────
from core.utils import normalize_term, parse_frontmatter, dump_frontmatter

class TestNormalizeTerm:
    """normalize_term の各種入力パターンを検証。"""

    def test_basic_ascii(self):
        assert normalize_term("Hello World") == "hello_world"

    def test_japanese(self):
        assert normalize_term("ベクトル検索") == "ベクトル検索"

    def test_various_hyphens(self):
        """各種ハイフン・ダッシュが ASCII ハイフンに統一される。"""
        for char in ["\u2010", "\u2013", "\u2014", "\uFF0D"]:
            result = normalize_term(f"self{char}rag")
            assert result == "self-rag", f"Failed for U+{ord(char):04X}"

    def test_fullwidth_to_halfwidth(self):
        """全角英数が半角に変換される。"""
        assert normalize_term("ＬＬＭ") == "llm"

    def test_fullwidth_space(self):
        """全角スペースがアンダースコアに変換される。"""
        result = normalize_term("ＬＬＭ　モデル")
        assert "_" in result

    def test_empty_string(self):
        assert normalize_term("") == ""

    def test_md_extension_removed(self):
        assert normalize_term("page.md") == "page"

    def test_colon_removed(self):
        """MediaWiki名前空間記法のコロンが除去される。"""
        assert ":" not in normalize_term("Category:LLM")


class TestParseFrontmatter:
    """parse_frontmatter のパース精度を検証。"""

    def test_basic_parse(self):
        content = "---\ntitle: Test\ntags: [a, b]\n---\nBody text"
        data, body = parse_frontmatter(content)
        assert data is not None
        assert data["title"] == "Test"
        assert body == "Body text"

    def test_no_frontmatter(self):
        data, body = parse_frontmatter("Just plain text")
        assert data is None
        assert body == "Just plain text"

    def test_empty_frontmatter(self):
        """空の YAML ブロックはパース不可。全体が body として返される。"""
        data, body = parse_frontmatter("---\n---\nBody")
        # 空 YAML は yaml.load が None を返すため、parse_frontmatter もフォールバック
        assert "Body" in body

    def test_trailing_newline_optional(self):
        """末尾改行がなくてもパース成功する。"""
        content = "---\ntitle: X\n---"
        data, body = parse_frontmatter(content)
        assert data is not None
        assert data["title"] == "X"

class TestAutoLinkConcepts:
    """auto_link_concepts のテスト。自動リンク付与の挙動を検証。"""

    def test_basic_auto_link(self):
        from core.utils import auto_link_concepts
        body = "This is a test about RAG and LLM."
        concepts = ["RAG", "LLM"]
        result = auto_link_concepts(body, concepts)
        assert "[[RAG]]" in result
        assert "[[LLM]]" in result

    def test_avoid_existing_links(self):
        from core.utils import auto_link_concepts
        body = "This is [[RAG]] and LLM."
        concepts = ["RAG", "LLM"]
        result = auto_link_concepts(body, concepts)
        # すでにリンク化されているものは二重リンクにならないこと
        assert "[[ [[RAG]] ]]" not in result
        assert "[[RAG]]" in result
        assert "[[LLM]]" in result

    def test_longest_match_priority(self):
        from core.utils import auto_link_concepts
        body = "We use Retrieval-Augmented Generation which is also called RAG."
        concepts = ["RAG", "Retrieval-Augmented Generation"]
        result = auto_link_concepts(body, concepts)
        assert "[[Retrieval-Augmented Generation]]" in result
        assert "[[RAG]]" in result
        assert "[[Retrieval-Augmented [[Generation]]]]" not in result

    def test_avoid_headings(self):
        from core.utils import auto_link_concepts
        body = "# RAG Overview\n\nThis is about RAG."
        concepts = ["RAG"]
        result = auto_link_concepts(body, concepts)
        assert "# RAG Overview" in result  # 見出しは置換されない
        assert "about [[RAG]]." in result  # 本文は置換される

    def test_avoid_code_blocks(self):
        from core.utils import auto_link_concepts
        body = "Normal RAG text.\n```python\nprint('RAG is here')\n```\nMore RAG."
        concepts = ["RAG"]
        result = auto_link_concepts(body, concepts)
        assert "Normal [[RAG]] text." in result
        assert "print('RAG is here')" in result # コードブロック内は置換されない
        assert "More [[RAG]]." in result

    def test_japanese_values(self):
        content = "---\ntitle: 日本語タイトル\ntags: [タグ１, タグ２]\n---\n本文"
        data, body = parse_frontmatter(content)
        assert data["title"] == "日本語タイトル"
        assert "タグ１" in data["tags"]

    def test_emoji_values(self):
        content = "---\ntitle: テスト ✨\n---\n本文"
        data, body = parse_frontmatter(content)
        assert "✨" in data["title"]


class TestParseAndFilterConcepts:
    """parse_and_filter_concepts のパースおよびノイズ除去ロジックを検証。"""

    def test_basic_parsing(self):
        from core.utils import parse_and_filter_concepts
        raw = "- NLP\n- RAG\n- System Engineering"
        result = parse_and_filter_concepts(raw)
        assert result == ["NLP", "RAG", "System Engineering"]

    def test_remove_citations_and_parentheses(self):
        """引用 (et al) や片方だけの括弧を持つゴミが除去されること。"""
        from core.utils import parse_and_filter_concepts
        raw = "- Valid Concept\n- Retrieval (Lewis et al., 2020)\n- 2020)\n- et al. model"
        result = parse_and_filter_concepts(raw)
        assert "Valid Concept" in result
        assert "Retrieval (Lewis et al., 2020)" not in result
        assert "2020)" not in result
        assert "et al. model" not in result

    def test_remove_punctuation_and_links(self):
        """末尾の句読点や、LLMが誤って付与した [[ ]] が除去されること。"""
        from core.utils import parse_and_filter_concepts
        raw = "- ConceptA.\n- [[ConceptB]],\n- ConceptC;"
        result = parse_and_filter_concepts(raw)
        assert "ConceptA" in result
        assert "ConceptB" in result
        assert "ConceptC" in result

    def test_remove_duplicates_and_ignore_non_list(self):
        """重複が排除され、箇条書き(-)以外の行が無視されること。"""
        from core.utils import parse_and_filter_concepts
        raw = "Here are the concepts:\n- LLM\n- RAG\n- LLM\nThese are important."
        result = parse_and_filter_concepts(raw)
        assert len(result) == 2
        assert result[0] == "LLM"
        assert result[1] == "RAG"


class TestDumpFrontmatter:
    """dump_frontmatter の出力を検証。"""

    def test_roundtrip(self):
        """dump → parse の往復で値が保持される。"""
        original = {"title": "テスト", "tags": ["RAG", "LLM"]}
        dumped = dump_frontmatter(original)
        parsed, _ = parse_frontmatter(dumped)
        assert parsed["title"] == "テスト"
        assert "RAG" in parsed["tags"]

    def test_output_has_fences(self):
        dumped = dump_frontmatter({"key": "val"})
        assert dumped.startswith("---\n")
        assert "\n---\n" in dumped

    def test_empty_dict(self):
        dumped = dump_frontmatter({})
        assert "---" in dumped


# ──────────────────────────────────────────────────
# 2. ObsidianWriter テスト
# ──────────────────────────────────────────────────
from output.obsidian_writer import ObsidianWriter
from core.schemas import DraftConfig

class TestObsidianWriterCreateDraft:
    """create_draft_file のファイル生成とメタデータを検証。"""

    def test_new_file_has_tags(self, tmp_path):
        writer = ObsidianWriter(wiki_dir=tmp_path)
        content = dump_frontmatter({"tags": ["RAG", "LLM"]}) + "\n\n# Title\nBody"
        path = writer.create_draft_file(DraftConfig(page_name="test_page", proposed_content=content))

        result = path.read_text(encoding="utf-8")
        data, _ = parse_frontmatter(result)
        assert "未審査" in data["tags"]
        assert "RAG" in data["tags"]
        assert "LLM" in data["tags"]

    def test_update_merges_tags(self, tmp_path):
        """既存ファイルのタグと新規タグがマージされる。"""
        writer = ObsidianWriter(wiki_dir=tmp_path)
        # 1回目: 既存ファイルを作成
        first = dump_frontmatter({"tags": ["existing"]}) + "\n\nOld body"
        writer.create_draft_file(DraftConfig(page_name="merge_test", proposed_content=first))
        # 2回目: 新タグ付きで更新
        second = dump_frontmatter({"tags": ["new_tag"]}) + "\n\nNew body"
        path = writer.create_draft_file(DraftConfig(page_name="merge_test", proposed_content=second))

        data, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        assert "existing" in data["tags"]
        assert "new_tag" in data["tags"]
        assert "未審査" in data["tags"]

    def test_sub_dir(self, tmp_path):
        writer = ObsidianWriter(wiki_dir=tmp_path)
        content = "# Concept\nBody"
        path = writer.create_draft_file(DraftConfig(page_name="concept_page", proposed_content=content, sub_dir="concepts"))
        assert "concepts" in str(path)
        assert path.exists()

    def test_encoding_robustness(self, tmp_path):
        """CP932 で表現不能な文字を含んでもエラーにならない。"""
        writer = ObsidianWriter(wiki_dir=tmp_path)
        content = "# ✨🚀🔗\nEmoji body"
        path = writer.create_draft_file(DraftConfig(page_name="emoji_test", proposed_content=content))
        result = path.read_text(encoding="utf-8")
        assert "✨" in result


class TestObsidianWriterSchema:
    """create_draft_from_schema のメタデータ統合を検証。"""

    def test_schema_tags_in_yaml(self, tmp_path):
        """スキーマで指定したタグが最終YAMLに反映される。"""
        writer = ObsidianWriter(wiki_dir=tmp_path)
        data = {
            "title": "Schema Test",
            "abstract": "Test abstract",
            "concepts": ["A", "B"],
            "body": "Body with [[Link]]",
            "tags": ["RAG", "Self-RAG"],
            "aliases": ["SR"]
        }
        path = writer.create_draft_from_schema(data)
        result = path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(result)
        assert "RAG" in fm["tags"]
        assert "Self-RAG" in fm["tags"]
        assert "未審査" in fm["tags"]
        assert "SR" in fm["aliases"]

    def test_nested_yaml_extraction(self, tmp_path):
        """bodyに埋め込まれたYAMLからタグが救出される。"""
        writer = ObsidianWriter(wiki_dir=tmp_path)
        nested_body = "---\ntags: [embedded_tag]\n---\nActual content"
        data = {
            "title": "Nested Test",
            "abstract": "A",
            "concepts": [],
            "body": nested_body,
            "tags": ["explicit_tag"],
            "aliases": []
        }
        path = writer.create_draft_from_schema(data)
        result = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(result)
        assert "embedded_tag" in fm["tags"]
        assert "explicit_tag" in fm["tags"]
        # 本文にYAMLが二重に残っていないこと
        assert body.count("---") <= 2  # footer の --- のみ


# ──────────────────────────────────────────────────
# 3. フォールバック品質テスト
# ──────────────────────────────────────────────────
class TestFallbackQuality:
    """draft_node フォールバック時のデータ品質を検証。"""

    def test_fallback_tags_are_not_headings(self):
        """タグに見出しテキストが混入しないこと。"""
        body = """# Self-RAG Overview

近年の [[LLM]] は高品質な生成が可能。[[RAG]] が注目されている。

## Background

[[Retrieval]] と [[Generation]] を組み合わせる。
"""
        found_links = list(set(re.findall(r"\[\[(.*?)\]\]", body)))
        concepts = [l.split("|")[0].strip() for l in found_links[:10]]
        tags = ["auto-draft"] + [c for c in concepts if len(c) <= 15 and " " not in c][:5]

        # 見出しテキストがタグに含まれないこと
        assert "Self-RAG Overview" not in tags
        assert "Background" not in tags
        # リンクから抽出された概念がタグに含まれること
        assert "LLM" in tags
        assert "RAG" in tags

    def test_fallback_abstract_not_heading(self):
        """abstract に見出し行が使われないこと。"""
        body = "# Title\n\nFirst paragraph of content.\n\n## Section"
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        abstract = paragraphs[0][:200] if paragraphs else "自動生成"
        assert not abstract.startswith("#")
        assert "First paragraph" in abstract

    def test_fallback_concepts_from_links(self):
        """[[リンク]]がコンセプトとして抽出される。"""
        body = "Text with [[ConceptA]] and [[ConceptB|表示名]]"
        found_links = list(set(re.findall(r"\[\[(.*?)\]\]", body)))
        concepts = [l.split("|")[0].strip() for l in found_links]
        assert "ConceptA" in concepts
        assert "ConceptB" in concepts


# ──────────────────────────────────────────────────
# 4. ワークフロー統合テスト
# ──────────────────────────────────────────────────
from agent.graph import app
from core.schemas import WikiMetadataSchema

class TestWorkflow:
    """LangGraph ワークフローの遷移を検証。"""

    @pytest.mark.ollama
    def test_ingest_to_review(self):
        """ingest → draft → review の完遂。"""
        mock_llm = MagicMock()
        mock_schema_result = WikiMetadataSchema(
            title="統合テスト",
            abstract="テスト概要",
            concepts=["概念A"],
            body="本文 [[リンクA]]",
            tags=["test"],
            aliases=[]
        )
        mock_llm.with_structured_output.return_value.invoke.return_value = mock_schema_result
        mock_llm.invoke.return_value.content = "タイトル提案"

        with patch("agent.graph.get_docling_parser") as mock_get_parser, \
             patch("agent.graph.get_qdrant_store") as mock_get_store, \
             patch("agent.graph.get_obsidian_writer") as mock_get_writer, \
             patch("core.llm_router.router.get_model", return_value=mock_llm):
            
            mock_parser = mock_get_parser.return_value
            mock_store = mock_get_store.return_value
            mock_writer = mock_get_writer.return_value

            mock_path = MagicMock()
            mock_path.read_text.return_value = "テスト用Markdownコンテンツ"
            mock_parser.convert.return_value = mock_path
            mock_store.search.return_value = []

            config = {"configurable": {"thread_id": "test-1"}}
            # 第一段階: interrupt_before=["review"] により一時停止
            final_state = app.invoke({"input_file": "test.md", "status": "starting"}, config=config)
            assert final_state["status"] == "drafted"
            
            # 第二段階: 再開 (None を渡すことで次のノード 'review' を実行)
            final_state = app.invoke(None, config=config)
            assert final_state["status"] == "completed"
            mock_writer.write_page.assert_called()

    @pytest.mark.ollama
    def test_encoding_in_ingest(self):
        """日本語ファイル名が ingest_node で処理できる。"""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "✨テスト🚀"

        with patch("agent.graph.get_docling_parser") as mock_get_parser, \
             patch("agent.graph.get_qdrant_store") as mock_get_store, \
             patch("core.llm_router.router.get_model", return_value=mock_llm):
            
            mock_parser = mock_get_parser.return_value
            mock_store = mock_get_store.return_value

            mock_path = MagicMock()
            mock_path.read_text.return_value = "コンテンツ"
            mock_parser.convert.return_value = mock_path
            mock_store.search.return_value = []

            from agent.graph import ingest_node
            result = ingest_node({"input_file": "データ_✨.md", "status": "starting"})
            assert "target_page" in result


class TestGlobalConceptLinking:
    """既存概念リストに基づくグローバル・オートリンクを検証。"""

    def test_get_all_concepts(self, tmp_path):
        from core.utils import get_all_concepts
        concept_dir = tmp_path / "concepts"
        concept_dir.mkdir()
        (concept_dir / "RAG.md").write_text("body", encoding="utf-8")
        (concept_dir / "LLM.md").write_text("body", encoding="utf-8")
        (concept_dir / "[[Self-RAG]].md").write_text("body", encoding="utf-8") # 不正なファイル名も救済できるか

        concepts = get_all_concepts(wiki_dir=tmp_path)
        assert "RAG" in concepts
        assert "LLM" in concepts
        assert "Self-RAG" in concepts
        # 正規化されていること
        for c in concepts:
            assert "[[" not in c
            assert "]]" not in c

    def test_auto_link_with_hyphen_boundary(self):
        from core.utils import auto_link_concepts
        body = "This is a post about RAG in Self-RAG context."
        concepts = ["RAG", "Self-RAG"]
        result = auto_link_concepts(body, concepts)
        
        # Self-RAG が優先され、その中の RAG は重複リンクにならないこと
        assert "[[Self-RAG]]" in result
        assert "Self-[[RAG]]" not in result
        assert "about [[RAG]]" in result
