import unittest
import os
import shutil
import pytest
from pathlib import Path
from agent.graph import app
from langgraph.types import Command

@pytest.mark.ollama
class TestAgentFlow(unittest.TestCase):
    def setUp(self):
        # テストデータのセットアップ
        self.raw_dir = Path("_raw")
        self.staged_dir = Path("_staged")
        self.wiki_dir = Path("wiki")
        
        self.test_file = self.raw_dir / "integration_test.txt"
        self.test_file.write_text("Recent advances in AI agents show that HITL is crucial.", encoding="utf-8")
        
        self.config = {"configurable": {"thread_id": "test_thread_agent_flow"}}

    def tearDown(self):
        # テストデータのクリーンアップ
        if self.test_file.exists():
            self.test_file.unlink()
        # _staged内の関連ファイルを削除
        for f in self.staged_dir.glob("integration_test*"):
            f.unlink()

    def test_full_flow_with_interrupt(self):
        # 1. 実行開始（reviewノードで一時停止するはず）
        initial_input = {"input_file": str(self.test_file)}
        
        # 最初の実行
        events = []
        for event in app.stream(initial_input, self.config, stream_mode="values"):
            events.append(event)
            # draft_nodeが終わった時点で status は 'drafted' になるはず
            if event.get("status") == "drafted":
                break
        
        # 中断されていることを確認
        state = app.get_state(self.config)
        self.assertEqual(state.next, ("review",)) # 中断されたノードが次に実行予定となる
        
        # review_node の前なので、まだファイルは生成されていないはず
        staged_files = [f.name for f in self.staged_dir.glob("*_review.md")]
        self.assertEqual(len(staged_files), 0, "Review file should not exist before review node.")

        # 2. 人間が 'approve' を送る（再開）
        # Command(resume="approve") を使用して再開
        for event in app.stream(None, self.config, stream_mode="values"):
            events.append(event)

        # 最終状態の確認
        final_state = app.get_state(self.config)
        # review_node が完了すると status は 'completed' になる
        self.assertEqual(final_state.values["status"], "completed")
        
        # Wikiに反映されているか確認 (review_node で作成される)
        # 実際には ObsidianWriter.create_draft_from_schema が _staged/ に書く
        staged_files = [f.name for f in self.staged_dir.glob("*.md")]
        self.assertTrue(len(staged_files) > 0, "No file found in _staged directory after review.")

if __name__ == '__main__':
    unittest.main()
