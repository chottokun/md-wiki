import unittest
import os
import shutil
from pathlib import Path
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

if __name__ == '__main__':
    unittest.main()
