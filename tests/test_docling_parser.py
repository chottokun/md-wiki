import unittest
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

class TestDoclingParser(unittest.TestCase):
    def setUp(self):
        # Setup mocking for docling
        self.mock_docling = MagicMock()
        self.mock_conv = MagicMock()
        self.mock_base = MagicMock()
        
        # Configure input formats
        self.mock_base.InputFormat.PDF = "pdf"
        self.mock_base.InputFormat.IMAGE = "image"
        self.mock_base.InputFormat.MD = "md"
        self.mock_base.InputFormat.DOCX = "docx"
        self.mock_base.InputFormat.PPTX = "pptx"
        self.mock_base.InputFormat.HTML = "html"

        self.patcher = patch.dict(sys.modules, {
            "docling": self.mock_docling,
            "docling.document_converter": self.mock_conv,
            "docling.datamodel.base_models": self.mock_base,
            "docling.datamodel.pipeline_options": MagicMock()
        })
        self.patcher.start()

        # Late import to ensure mocks are used
        from ingestion.docling_parser import DoclingParser
        self.parser = DoclingParser(output_dir="tests/test_data_staged")
        self.test_file = Path("tests/test_file.txt")
        self.test_file.write_text("Hello docling", encoding="utf-8")

    def tearDown(self):
        self.patcher.stop()
        if hasattr(self, 'test_file') and self.test_file.exists():
            self.test_file.unlink()
        shutil.rmtree("tests/test_data_staged", ignore_errors=True)

    def test_convert_txt_to_md(self):
        # Configure the mock to return a document with markdown content
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test Header\nThis is a test document."
        self.parser.converter.convert.return_value = mock_result

        output_path = self.parser.convert(str(self.test_file))
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.exists())
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("# Test Header", content)

    def test_convert_invalid_file(self):
        # 存在しないファイルの場合は変換を行わずに None を返す
        output_path = self.parser.convert("non_existent_file.pdf")
        self.assertIsNone(output_path)

    def test_convert_exception(self):
        # converter.convert が Exception を投げるようにモック
        with patch.object(self.parser.converter, 'convert', side_effect=Exception("Test Error")):
            with self.assertLogs('ingestion.docling_parser', level='ERROR') as cm:
                output_path = self.parser.convert(str(self.test_file))

                # 戻り値が None であることの確認
                self.assertIsNone(output_path)

                # エラーログが出力されていることの確認
                self.assertTrue(any("の変換中にエラーが発生しました: Test Error" in output for output in cm.output))

if __name__ == '__main__':
    unittest.main()
