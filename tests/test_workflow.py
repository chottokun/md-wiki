import unittest
from unittest.mock import patch, MagicMock
import pytest
from agent.graph import app
from core.schemas import WikiMetadataSchema

@pytest.mark.ollama
def test_full_workflow_ingest_to_review():
    """ワークフローが ingest -> draft -> review と完遂するかテストする。"""

    # LLMのモック
    mock_llm = MagicMock()
    # WikiMetadataSchema のモックデータを返すように設定
    mock_schema_result = WikiMetadataSchema(
        title="統合テスト",
        abstract="テスト概要",
        concepts=["概念A", "概念B"],
        body="本文 [[リンクA]]",
        tags=["test"],
        aliases=[]
    )
    mock_llm.with_structured_output.return_value.invoke.return_value = mock_schema_result
    mock_llm.invoke.return_value.content = "タイトル提案"

    # 外部依存のモック（Factory関数をパッチ）
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

        # ワークフローの実行
        config = {"configurable": {"thread_id": "test-workflow-thread"}}
        # reviewノードで中断される
        final_state = app.invoke({"input_file": "dummy.pdf", "status": "starting"}, config=config)
        
        # 検証
        assert final_state["status"] == "reviewed"
        # factory経由で取得されたwriterのメソッドが呼ばれたか
        mock_writer.create_draft_file.assert_called()

@pytest.mark.ollama
def test_encoding_in_workflow():
    """日本語名や特殊文字を含むファイルがワークフローで正しく処理されるか。"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "✨特殊タイトル🚀"

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
        
        assert result["status"] == "ingested"
        assert "target_page" in result
        assert "データ_✨.md" in result["source_filename"]

if __name__ == '__main__':
    pytest.main([__file__])
