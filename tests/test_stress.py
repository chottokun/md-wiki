import unittest
import os
import time
from retrieval.qdrant_store import QdrantHybridStore

class TestSystemStress(unittest.TestCase):
    """
    システムの限界と極端なデータ入力に対する耐性の検証。
    """
    
    @classmethod
    def setUpClass(cls):
        cls.store = QdrantHybridStore(collection_name="stress_test_collection")

    @classmethod
    def tearDownClass(cls):
        cls.store.delete_collection()

    def test_massive_text_chunking(self):
        """巨大なテキスト（10万文字）のチャンク化と登録の安定性。"""
        massive_text = "これはテスト用の超長文です。 " * 10000 # 10万文字以上
        start_time = time.time()
        
        # 登録
        self.store.add_text(massive_text, {"source": "massive_doc", "type": "raw_source"})
        end_time = time.time()
        
        print(f"\n[Stress Test] 100k characters indexed in {end_time - start_time:.2f} seconds.")
        
        # 検索
        results = self.store.search("テスト用", k=5)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].metadata["source"], "massive_doc")

    def test_special_characters_robustness(self):
        """特殊文字、絵文字、空行が連続する複雑なMarkdownへの耐性。"""
        complex_md = """
# 🐉 特殊テスト !@#$%^&*()
- 🛠️ 絵文字の混入
- \t タブと \n 空行の連続
- <script>alert('XSS')</script> HTMLタグの混入
- 
- 
- [ ] 空のタスク
- リンク切れ: [[ ]]
        """
        # 登録してもエラーにならないこと
        try:
            self.store.add_text(complex_md, {"source": "complex_doc", "type": "wiki_page"})
        except Exception as e:
            self.fail(f"Special characters caused a crash: {e}")
            
        results = self.store.search("絵文字", k=1)
        self.assertTrue(len(results) > 0)

if __name__ == '__main__':
    unittest.main()
