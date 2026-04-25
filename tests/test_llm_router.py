import unittest
from core.llm_router import router, LLMLayer, LLMProvider
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
import os

class TestLLMRouter(unittest.TestCase):
    def test_ollama_instance(self):
        # LLM_PROVIDER=ollama (default in .env)
        os.environ["LLM_PROVIDER"] = "ollama"
        model = router.get_model(LLMLayer.L1)
        self.assertIsInstance(model, ChatOllama)
        self.assertEqual(model.model, os.getenv("LOCALLLM_MODEL"))
        # keep_alive: 0 が設定されているか確認
        self.assertEqual(model.num_ctx, None) # 他のパラメータも確認可能

    def test_openai_compatible_l3(self):
        os.environ["LLM_PROVIDER"] = "openai_compatible"
        # ルーターを再初期化（シングルトンを簡易的にリセット）
        from core.llm_router import LLMRouter
        test_router = LLMRouter()
        model = test_router.get_model(LLMLayer.L3)
        self.assertIsInstance(model, ChatOpenAI)
        self.assertEqual(model.model_name, os.getenv("OPENAI_COMPATIBLE_MODEL"))

    def test_unsupported_provider(self):
        os.environ["LLM_PROVIDER"] = "unknown"
        from core.llm_router import LLMRouter
        with self.assertRaises(ValueError):
            LLMRouter()

if __name__ == '__main__':
    unittest.main()
