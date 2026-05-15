import unittest
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

class TestDoclingParser(unittest.TestCase):
    def setUp(self):
        # ingestion.docling_parser 内の DocumentConverter をパッチ
        self.mock_conv_patcher = patch("ingestion.docling_parser.DocumentConverter")
        self.mock_conv_class = self.mock_conv_patcher.start()
        self.mock_converter_instance = self.mock_conv_class.return_value

        from ingestion.docling_parser import DoclingParser
        self.parser = DoclingParser(output_dir="tests/test_data_staged")
        self.test_file = Path("tests/test_file.txt")
        self.test_file.write_text("Hello docling", encoding="utf-8")

    def tearDown(self):
        self.mock_conv_patcher.stop()
        if hasattr(self, 'test_file') and self.test_file.exists():
            self.test_file.unlink()
        shutil.rmtree("tests/test_data_staged", ignore_errors=True)

    def test_convert_txt_to_md(self):
        # Configure the mock to return a document with markdown content
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test Header\nThis is a test document."
        self.mock_converter_instance.convert.return_value = mock_result

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
        self.mock_converter_instance.convert.side_effect = Exception("Test Error")
        with self.assertLogs('ingestion.docling_parser', level='ERROR') as cm:
            output_path = self.parser.convert(str(self.test_file))

            # 戻り値が None であることの確認
            self.assertIsNone(output_path)

            # エラーログが出力されていることの確認
            self.assertTrue(any("の変換中にエラーが発生しました: Test Error" in output for output in cm.output))

if __name__ == '__main__':
    unittest.main()
