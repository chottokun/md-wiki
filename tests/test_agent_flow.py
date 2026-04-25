import unittest
import os
import shutil
from pathlib import Path
from agent.graph import app
from langgraph.types import Command

class TestAgentFlow(unittest.TestCase):
    def setUp(self):
        # テストデータのセットアップ
        self.raw_dir = Path("_raw")
        self.staged_dir = Path("_staged")
        self.wiki_dir = Path("wiki")
        
        self.test_file = self.raw_dir / "integration_test.txt"
        self.test_file.write_text("Recent advances in AI agents show that HITL is crucial.")
        
        self.config = {"configurable": {"thread_id": "test_thread"}}

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
            if event.get("status") == "reviewed":
                break
        
        # 中断されていることを確認
        state = app.get_state(self.config)
        self.assertEqual(state.next, ("review",)) # 中断されたノードが次に実行予定となる
        self.assertIn("integration_test_review.md", [f.name for f in self.staged_dir.iterdir()])

        # 2. 人間が 'approve' を送る（再開）
        # Command(resume="approve") を使用して再開
        for event in app.stream(Command(resume="approve"), self.config, stream_mode="values"):
            events.append(event)

        # 最終状態の確認
        final_state = app.get_state(self.config)
        self.assertEqual(final_state.values["status"], "applied")
        
        # Wikiに反映されているか確認
        wiki_path = self.wiki_dir / "integration_test.md"
        self.assertTrue(wiki_path.exists())

if __name__ == '__main__':
    unittest.main()
