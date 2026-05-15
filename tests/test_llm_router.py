import unittest
import os
import pytest
from unittest.mock import patch
from core.llm_router import LLMRouter, LLMLayer, LLMProvider
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

class TestLLMRouter(unittest.TestCase):
    def test_ollama_instance(self):
        # LLM_PROVIDER=ollama を確実に適用した状態でインスタンス化
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama", "LOCALLLM_BASE_URL": "http://localhost:11434"}):
            router = LLMRouter()
            model = router.get_model(LLMLayer.L1)
            self.assertIsInstance(model, ChatOllama)

    def test_openai_compatible_l3(self):
        # L3はプロバイダーによらず、現状は OpenAI 互換 (sakura-v1) と想定（Routerの実装に依存）
        # ただしプロバイダーが ollama の場合は ollama が返るようになっている
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai_compatible", "OPENAI_COMPATIBLE_BASE_URL": "https://api.ai.sakura.ad.jp/v1/"}):
            router = LLMRouter()
            model = router.get_model(LLMLayer.L3)
            self.assertIsInstance(model, ChatOpenAI)
            self.assertIn("sakura.ad.jp", model.openai_api_base)

    def test_unsupported_provider(self):
        # 未対応のプロバイダーが指定された場合の挙動
        # 注意: LLMProvider(value) は Enum にない値だと ValueError を投げる
        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}):
            router = LLMRouter()
            with self.assertRaises(NotImplementedError):
                router.get_model(LLMLayer.L1)

if __name__ == '__main__':
    unittest.main()
