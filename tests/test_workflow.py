import pytest
from unittest.mock import MagicMock, patch
from agent.graph import app
from agent.state import AgentState
from core.schemas import WikiPageSchema

def test_full_workflow_ingest_to_review():
    """ワークフローが ingest -> draft -> review と完遂するかテストする。"""
    
    # LLMのモック
    mock_llm = MagicMock()
    # WikiPageSchema のモックデータを返すように設定
    mock_schema_result = WikiPageSchema(
        title="統合テスト",
        abstract="テスト概要",
        concepts=["概念A", "概念B"],
        body="本文 [[リンクA]]",
        tags=["test"],
        aliases=[]
    )
    mock_llm.with_structured_output.return_value.invoke.return_value = mock_schema_result
    mock_llm.invoke.return_value.content = "タイトル提案"
    
    # 外部依存のモック
    with patch("agent.graph.docling_parser.convert") as mock_convert, \
         patch("agent.graph.qdrant_store.search") as mock_search, \
         patch("agent.graph.obsidian_writer.create_draft_from_schema") as mock_save, \
         patch("core.llm_router.router.get_model", return_value=mock_llm):
        
        # Doclingの戻り値を設定
        mock_path = MagicMock()
        mock_path.read_text.return_value = "テスト用Markdownコンテンツ"
        mock_convert.return_value = mock_path
        mock_search.return_value = []
        
        # 実行
        initial_state = {
            "input_file": "test.md",
            "status": "starting"
        }
        
        # ワークフローを実行 (thread_idが必要)
        config = {"configurable": {"thread_id": "test-thread"}}
        # 第一段階: interrupt_before=["review"] により一時停止
        final_state = app.invoke(initial_state, config=config)
        
        # 検証
        # ステータスは一時停止時点で 'drafted' になっているはず
        assert final_state["status"] == "drafted"

        # 第二段階: 再開 (None を渡すことで次のノード 'review' を実行)
        final_state = app.invoke(None, config=config)
        
        # 検証
        # 1. 各ノードを通ったか（ステータスの変遷）
        # ステータスは最終的に 'completed' (review_nodeの戻り値) になっているはず
        assert final_state["status"] == "completed"
        
        # 2. ファイル保存が呼ばれたか
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert saved_data["title"] == "統合テスト"

def test_encoding_in_workflow():
    """日本語名や特殊文字を含むファイルがワークフローで正しく処理されるか。"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "✨特殊タイトル🚀"
    
    with patch("agent.graph.docling_parser.convert") as mock_convert, \
         patch("core.llm_router.router.get_model", return_value=mock_llm):
        
        mock_path = MagicMock()
        mock_path.read_text.return_value = "コンテンツ"
        mock_convert.return_value = mock_path
        
        # 日本語ファイル名
        state = {"input_file": "データ_✨.md", "status": "starting"}
        
        # ingest_node だけ実行してテスト
        from agent.graph import ingest_node
        result = ingest_node(state)
        
        assert "target_page" in result
        # normalize_term によって安全な名前になっていること
        assert "特殊タイトル" in result["target_page"]
