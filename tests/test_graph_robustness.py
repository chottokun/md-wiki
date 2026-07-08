import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from agent.graph import _batch_fetch_context

def test_batch_fetch_context_with_list_content():
    """LLMが返すMessageのcontentがリスト形式の場合でも、safe_get_contentによってクラッシュせず処理されることを検証する。"""
    
    mock_store = MagicMock()
    # 最初の検索で evidences が見つからず、翻訳が必要と判定される設定
    mock_store.search_batch.side_effect = [
        [[]],  # results1: 空のリスト（evidencesなし）
        [[]]   # results2: 翻訳後の英語名での検索結果（空）
    ]
    
    # LLMの応答をモック。contentに文字列ではなく、辞書のリスト（LangChainなどの形式）を返す
    mock_llm = MagicMock()
    mock_response = AIMessage(content=[{"text": "translated_term"}])
    mock_llm.batch.return_value = [mock_response]
    
    terms = ["日本語用語"]
    
    with patch("agent.graph.get_qdrant_store", return_value=mock_store):
        # 実際に _batch_fetch_context を呼び出す
        # safe_get_contentが正しく機能していれば、リストのcontentから 'translated_term' が抽出され、
        # res.content.strip() で発生していた AttributeError: 'list' object has no attribute 'strip' が防がれます。
        # (store.search_batch に 'translated_term' が渡されるはず)
        
        # タイムアウト等の副作用を防ぐために、storeなどをパッチ
        result = _batch_fetch_context(terms, mock_llm)
        
        # 検証: 翻訳後の英語名で再検索が行われていること
        mock_store.search_batch.assert_any_call(["translated_term"], k=8)
        assert "日本語用語" in result
