import pytest
import logging
from unittest.mock import MagicMock
from agent.graph import draft_node, refine_node
from agent.state import AgentState

def test_draft_node_fallback_on_invalid_json():
    """LLMが不正なJSONを返した場合にフォールバックが正しく機能するかテストする。"""
    
    # モックの作成
    mock_llm = MagicMock()
    # with_structured_output はエラーを投げるように設定
    mock_llm.with_structured_output.return_value.invoke.side_effect = Exception("Invalid JSON from LLM")
    # フォールバック用の invoke は通常の文字列を返すように設定
    mock_llm.invoke.return_value.content = "これはフォールバックされた生テキストです。"
    
    # routerをモック（グローバルなrouterに影響を与えないよう工夫が必要だが、ここでは簡易化）
    import core.llm_router
    original_get_model = core.llm_router.router.get_model
    core.llm_router.router.get_model = MagicMock(return_value=mock_llm)
    
    state: AgentState = {
        "target_page": "テストページ",
        "raw_markdown": "新規情報",
        "retrieved_docs": [],
        "status": "starting"
    }
    
    try:
        result = draft_node(state)
        
        # 検証
        assert result["status"] == "drafted"
        assert "proposed_data" in result
        # フォールバックデータが生成されていること
        data = result["proposed_data"]
        assert data["title"] == "テストページ"
        assert data["body"] == "これはフォールバックされた生テキストです。"
        assert "auto-draft" in data["tags"]
        
    finally:
        # モックを元に戻す
        core.llm_router.router.get_model = original_get_model

def test_refine_node_fallback():
    """洗練ノードのフォールバックをテスト。"""
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.side_effect = Exception("Validation Error")
    mock_llm.invoke.return_value.content = "洗練後の生テキスト"
    
    import core.llm_router
    original_get_model = core.llm_router.router.get_model
    core.llm_router.router.get_model = MagicMock(return_value=mock_llm)
    
    state: AgentState = {
        "target_page": "既存ページ",
        "raw_markdown": "差分情報",
        "retrieved_docs": [],
        "status": "refining"
    }
    
    try:
        result = refine_node(state)
        assert result["status"] == "refined"
        assert result["proposed_data"]["body"] == "洗練後の生テキスト"
    finally:
        core.llm_router.router.get_model = original_get_model
