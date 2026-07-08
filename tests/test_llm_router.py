import unittest
import os
import pytest
from unittest.mock import patch
from core.llm_router import LLMRouter, LLMLayer, LLMProvider
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

class TestLLMRouter(unittest.TestCase):
    def test_ollama_instance(self):
        # LLM_PROVIDER=ollama (default in .env)
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama", "LOCALLLM_MODEL": "gemma4:latest"}):
            from core.llm_router import LLMRouter
            test_router = LLMRouter()
            model = test_router.get_model(LLMLayer.L1)
            self.assertIsInstance(model, ChatOllama)
            self.assertEqual(model.model, "gemma4:latest")
            # keep_alive: 0 が設定されているか確認
            self.assertEqual(model.num_ctx, None) # 他のパラメータも確認可能

    def test_openai_compatible_l3(self):
        # L3はプロバイダーによらず、現状は OpenAI 互換 (sakura-v1) と想定（Routerの実装に依存）
        # ただしプロバイダーが ollama の場合は ollama が返るようになっている
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "openai_compatible",
            "OPENAI_COMPATIBLE_BASE_URL": "https://api.ai.sakura.ad.jp/v1/",
            "OPENAI_API_KEY": "fake-key"
        }):
            router = LLMRouter()
            model = router.get_model(LLMLayer.L3)
            self.assertIsInstance(model, ChatOpenAI)
            self.assertIn("sakura.ad.jp", model.openai_api_base)

    def test_unsupported_provider(self):
        # 未対応のプロバイダーが指定された場合の挙動
        # 注意: LLMProvider(value) は Enum にない値だと ValueError を投げる
        with patch.dict(os.environ, {"LLM_PROVIDER": "unsupported"}):
            with self.assertRaises(ValueError):
                LLMRouter()

    def test_gemini_provider(self):
        # Geminiプロバイダーが指定された場合の挙動
        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "GEMINI_API": "fake-key"}):
            router = LLMRouter()
            from langchain_google_genai import ChatGoogleGenerativeAI
            model = router.get_model(LLMLayer.L1)
            self.assertIsInstance(model, ChatGoogleGenerativeAI)

    def test_get_language_instruction_default(self):
        # TARGET_LANGUAGE が設定されていない場合（デフォルトは Japanese）
        with patch.dict(os.environ, {}, clear=True):
            router = LLMRouter()
            instruction = router.get_language_instruction()
            self.assertEqual(instruction, "必ずJapaneseで回答・出力してください。")

    def test_get_language_instruction_custom_en(self):
        # TARGET_LANGUAGE が English の場合
        with patch.dict(os.environ, {"TARGET_LANGUAGE": "English"}):
            router = LLMRouter()
            instruction = router.get_language_instruction()
            self.assertEqual(instruction, "必ずEnglishで回答・出力してください。")

    def test_get_language_instruction_custom_jp(self):
        # TARGET_LANGUAGE が 日本語 の場合
        with patch.dict(os.environ, {"TARGET_LANGUAGE": "日本語"}):
            router = LLMRouter()
            instruction = router.get_language_instruction()
            self.assertEqual(instruction, "必ず日本語で回答・出力してください。")

if __name__ == '__main__':
    unittest.main()
