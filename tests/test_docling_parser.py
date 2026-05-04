import unittest
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock docling modules before importing DoclingParser
mock_docling_conv = MagicMock()
mock_docling_base = MagicMock()
mock_docling_pipe = MagicMock()

sys.modules["docling"] = MagicMock()
sys.modules["docling.document_converter"] = mock_docling_conv
sys.modules["docling.datamodel.base_models"] = mock_docling_base
sys.modules["docling.datamodel.pipeline_options"] = mock_docling_pipe

# Configure mocks to satisfy DoclingParser initialization
mock_docling_base.InputFormat.PDF = "pdf"
mock_docling_base.InputFormat.IMAGE = "image"
mock_docling_base.InputFormat.MD = "md"

from ingestion.docling_parser import DoclingParser

class TestDoclingParser(unittest.TestCase):
    def setUp(self):
        self.test_raw_dir = Path("tests/test_data_raw")
        self.test_staged_dir = Path("tests/test_data_staged")
        self.test_raw_dir.mkdir(parents=True, exist_ok=True)
        self.test_staged_dir.mkdir(parents=True, exist_ok=True)
        
        # テスト用のダミーテキストファイル作成
        self.test_file = self.test_raw_dir / "test.txt"
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("# Test Header\nThis is a test document.")
            
        self.parser = DoclingParser(output_dir=str(self.test_staged_dir))

    def tearDown(self):
        # テストデータの削除
        shutil.rmtree("tests/test_data_raw", ignore_errors=True)
        shutil.rmtree("tests/test_data_staged", ignore_errors=True)

    def test_convert_txt_to_md(self):
        # Configure the mock to return a document with markdown content
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test Header\nThis is a test document."
        self.parser.converter.convert.return_value = mock_result

        output_path = self.parser.convert(str(self.test_file))
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.suffix, ".md")
        
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Test Header", content)

    def test_file_not_found(self):
        output_path = self.parser.convert("non_existent_file.pdf")
        self.assertIsNone(output_path)

    def test_convert_exception(self):
        # self.parser.converter.convert が Exception を投げるようにモック
        with patch.object(self.parser.converter, 'convert', side_effect=Exception("Test Error")):
            with self.assertLogs('ingestion.docling_parser', level='ERROR') as cm:
                output_path = self.parser.convert(str(self.test_file))

                # 戻り値が None であることの確認
                self.assertIsNone(output_path)

                # エラーログが出力されていることの確認
                self.assertTrue(any("の変換中にエラーが発生しました: Test Error" in output for output in cm.output))

if __name__ == '__main__':
    unittest.main()
