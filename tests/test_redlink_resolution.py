import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from agent.graph import app
from core.schemas import WikiMetadataSchema

@pytest.mark.ollama
class TestRedlinkResolution(unittest.TestCase):
    def setUp(self):
        self.wiki_dir = Path("tests/test_wiki_redlinks")
        self.wiki_dir.mkdir(exist_ok=True)
        # 既存ページを作成
        (self.wiki_dir / "ExistingPage.md").write_text("See [[MissingPage]] for details.", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.wiki_dir, ignore_errors=True)

    @patch('agent.graph.get_qdrant_store')
    @patch('agent.graph.get_obsidian_writer')
    @patch('core.llm_router.LLMRouter.get_model')
    def test_lint_creates_draft_for_redlink_with_evidence(self, mock_get_model, mock_get_writer, mock_get_store):
        """
        赤リンク（MissingPage）を検知し、Qdrantから証拠が見つかった場合にスタブを作成するか。
        """
        # 1. モックの設定
        mock_store = mock_get_store.return_value
        mock_writer = mock_get_writer.return_value
        mock_writer.wiki_dir = self.wiki_dir
        
        # 検索結果（証拠）を返すように設定
        from langchain_core.documents import Document
        mock_store.search.return_value = [
            Document(page_content="MissingPage is a known technique.", metadata={"source": "Doc.pdf", "type": "raw_source"})
        ]
        
        # LLMのモック
        mock_model = MagicMock()
        # 翻訳用、本文生成用、メタデータ抽出用の3回呼ばれる想定
        mock_model.invoke.side_effect = [
            MagicMock(content="MissingPage"), # 翻訳
            MagicMock(content="Generated Body"), # 本文
            MagicMock(content="Generated Fallback Concepts") # フォールバック概念
        ]
        # 構造化出力
        mock_metadata = WikiMetadataSchema(
            title="MissingPage", abstract="Summary", concepts=["Concept"], body="Body", tags=["test"], aliases=[]
        )
        mock_model.with_structured_output.return_value.invoke.return_value = mock_metadata
        mock_get_model.return_value = mock_model
        
        # 2. 実行
        from agent.graph import lint_node
        result = lint_node({"status": "starting_lint"})
        
        # 3. 検証
        self.assertEqual(result["status"], "linted")
        # writer.create_draft_from_schema が呼ばれたか
        mock_writer.create_draft_from_schema.assert_called()

if __name__ == '__main__':
    unittest.main()
