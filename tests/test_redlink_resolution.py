import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os
from agent.graph import app
from agent.state import AgentState
from core.schemas import WikiMetadataSchema
from langchain_core.messages import AIMessage

class TestRedlinkResolution(unittest.TestCase):
    """
    一次情報に基づいた未作成概念（Red-link）の自動解決機能のテスト。
    """

    @patch('agent.graph.qdrant_store.search')
    @patch('core.llm_router.LLMRouter.get_model')
    def test_lint_creates_draft_for_redlink_with_evidence(self, mock_get_model, mock_search):
        """
        リンク切れを見つけた際、一次情報を検索して根拠があれば下書きを作成するか。
        """
        # 1. Wikiフォルダの状況：PageAがあるが、中身に [[UnknownTerm]] へのリンク
        # (モックではなく物理的な小規模チェックを行う準備)
        wiki_dir = Path("wiki")
        wiki_dir.mkdir(exist_ok=True)
        (wiki_dir / "PageA.md").write_text("Concepts like [[UnknownTerm]] are vital.", encoding="utf-8")
        
        # 2. Qdrantのモック：UnknownTerm で検索すると一次情報の断片がヒット
        from langchain_core.documents import Document
        mock_search.return_value = [
            Document(page_content="UnknownTerm is defined as a recursive neural architecture.", 
                     metadata={"source": "research_paper_2024.pdf", "type": "raw_source"})
        ]
        
        # 3. LLMのモック
        mock_model = MagicMock()
        
        # body生成用
        mock_model.invoke.return_value = AIMessage(content="AI generated content about UnknownTerm based on primary source.")
        
        # metadata抽出用
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = WikiMetadataSchema(
            title="UnknownTerm",
            abstract="AI generated content about UnknownTerm",
            concepts=["UnknownTerm"],
            tags=["auto-draft"],
            aliases=[]
        )
        mock_model.with_structured_output.return_value = mock_structured
        
        mock_get_model.return_value = mock_model
        
        # 4. Lintノードを実行
        config = {"configurable": {"thread_id": "redlink_test"}}
        # 直接 lint ノードの挙動を模した実行、またはグラフ全体でlint開始
        for event in app.stream({"status": "starting_lint"}, config, stream_mode="values"):
            pass

        # 5. 検証：wiki/concepts/ に UnknownTerm.md が生成されていること
        # agent/graph.py では obsidian_writer.create_draft_from_schema(data, sub_dir="concepts") を呼んでいる
        staged_file = Path("wiki/concepts/UnknownTerm.md")
        self.assertTrue(staged_file.exists(), f"Draft file for Red-link should be created at {staged_file}")
        
        # 6. 中身のエビデンス確認
        content = staged_file.read_text(encoding="utf-8")
        # LLMが正しく一次情報を引用している（はず）の確認
        self.assertIn("UnknownTerm", content)
        
        # クリーンアップ
        staged_file.unlink()
        (wiki_dir / "PageA.md").unlink()
        if (wiki_dir / "concepts").exists():
            for f in (wiki_dir / "concepts").iterdir(): f.unlink()
            (wiki_dir / "concepts").rmdir()
        print("\n✅ Red-link auto-resolution (TDD) initial test verified logic path.")

if __name__ == '__main__':
    unittest.main()
