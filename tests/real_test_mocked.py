import unittest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(os.path.abspath(os.curdir))

class RealTestMocked(unittest.TestCase):
    """
    リファクタリング後の WikiQueryEngine が正しく動作することを確認するモックテスト。
    """

    @patch('retrieval.query_engine.WikiQueryEngine.query')
    @patch('output.obsidian_writer.ObsidianWriter.add_log_entry')
    def test_run_query_integration(self, mock_log, mock_query):
        # 1. 依存関係のモック化
        mock_query.return_value = "Mocked answer: RAG is Retrieval-Augmented Generation."
        
        # 2. main.run_query の実行
        from main import run_query
        print("\n--- Start Real-style Mock Test ---")
        run_query("RAGとは？")
        print("--- End Real-style Mock Test ---\n")

        # 3. 検証
        mock_query.assert_called_with("RAGとは？")
        self.assertTrue(mock_log.called)
        
        print("✅ main.run_query が WikiQueryEngine を正しく利用していることが確認されました。")

    @patch('agent.graph.app.stream')
    @patch('main.run_git_commit')
    def test_run_workflow_ingest(self, mock_commit, mock_stream):
        # ワークフローの動作をシミュレート
        mock_stream.return_value = [
            {"status": "ingested", "target_page": "TestPage"},
            {"status": "completed", "target_page": "TestPage"}
        ]
        
        from main import run_workflow
        run_workflow({"input_file": "_raw/test.pdf"}, auto_approve=True)
        
        self.assertTrue(mock_stream.called)
        self.assertTrue(mock_commit.called)
        print("✅ main.run_workflow がエージェントグラフを正しく呼び出し、コミットを行っています。")

if __name__ == '__main__':
    unittest.main()
