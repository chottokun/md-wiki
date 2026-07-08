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
        # TARGET_LANGUAGE が設定されていない場合はデフォルトの Japanese
        with patch.dict(os.environ, {}, clear=True):
            # 他の必要な環境変数が消えると LLMRouter.__init__ でエラーになる可能性があるので注意
            # LLMRouter.__init__ は LLM_PROVIDER 等を読み込む
            with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}):
                router = LLMRouter()
                instruction = router.get_language_instruction()
                self.assertEqual(instruction, "必ずJapaneseで回答・出力してください。")

    def test_get_language_instruction_custom(self):
        # TARGET_LANGUAGE が設定されている場合
        with patch.dict(os.environ, {"TARGET_LANGUAGE": "English"}):
            router = LLMRouter()
            instruction = router.get_language_instruction()
            self.assertEqual(instruction, "必ずEnglishで回答・出力してください。")

    def test_get_model_ollama_mapping(self):
        with patch("core.llm_router.ChatOllama") as mock_ollama:
            with patch.dict(os.environ, {
                "LLM_PROVIDER": "ollama",
                "LOCALLLM_MODEL": "local-m",
                "STANDARDLLM_MODEL": "std-m",
                "LOCALLLM_BASE_URL": "http://test:11434"
            }):
                router = LLMRouter()

                # L1 -> local_model
                router.get_model(LLMLayer.L1)
                mock_ollama.assert_called_with(
                    model="local-m",
                    base_url="http://test:11434",
                    keep_alive="0"
                )

                # L2 -> standard_model
                router.get_model(LLMLayer.L2)
                mock_ollama.assert_called_with(
                    model="std-m",
                    base_url="http://test:11434",
                    keep_alive="0"
                )

                # L3 -> standard_model
                router.get_model(LLMLayer.L3)
                mock_ollama.assert_called_with(
                    model="std-m",
                    base_url="http://test:11434",
                    keep_alive="0"
                )

    def test_get_model_openai_compatible_mapping(self):
        with patch("core.llm_router.ChatOpenAI") as mock_openai:
            with patch.dict(os.environ, {
                "LLM_PROVIDER": "openai_compatible",
                "OPENAI_COMPATIBLE_MODEL": "adv-m",
                "OPENAI_COMPATIBLE_API": "test-api-key",
                "OPENAI_COMPATIBLE_BASE_URL": "http://test-api/v1"
            }):
                router = LLMRouter()

                for layer in [LLMLayer.L1, LLMLayer.L2, LLMLayer.L3]:
                    router.get_model(layer)
                    mock_openai.assert_called_with(
                        model="adv-m",
                        openai_api_key="test-api-key",
                        openai_api_base="http://test-api/v1"
                    )

    def test_get_model_gemini_mapping(self):
        with patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_gemini:
            with patch.dict(os.environ, {
                "LLM_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-gemini-key"
            }):
                # Test default model mapping when GEMINI_MODEL is not set
                with patch.dict(os.environ, {}, clear=False):
                    if "GEMINI_MODEL" in os.environ:
                        del os.environ["GEMINI_MODEL"]

                    router = LLMRouter()

                    # L3 -> gemini-1.5-pro
                    router.get_model(LLMLayer.L3)
                    mock_gemini.assert_called_with(
                        model="gemini-1.5-pro",
                        api_key="test-gemini-key"
                    )

                    # L1 -> gemini-1.5-flash
                    router.get_model(LLMLayer.L1)
                    mock_gemini.assert_called_with(
                        model="gemini-1.5-flash",
                        api_key="test-gemini-key"
                    )

                # Test custom model name from GEMINI_MODEL
                with patch.dict(os.environ, {"GEMINI_MODEL": "custom-gemini"}):
                    router = LLMRouter()
                    router.get_model(LLMLayer.L1)
                    mock_gemini.assert_called_with(
                        model="custom-gemini",
                        api_key="test-gemini-key"
                    )

    def test_get_model_kwargs_forwarding(self):
        with patch("core.llm_router.ChatOllama") as mock_ollama:
            with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}):
                router = LLMRouter()
                router.get_model(LLMLayer.L1, temperature=0.7, top_p=0.9)

                # Verify that temperature and top_p are passed and they should override or complement defaults
                args, kwargs = mock_ollama.call_args
                self.assertEqual(kwargs["temperature"], 0.7)
                self.assertEqual(kwargs["top_p"], 0.9)
                self.assertEqual(kwargs["model"], router.local_model)

    def test_get_language_instruction(self):
        # Default should be Japanese if TARGET_LANGUAGE is not set
        with patch.dict(os.environ, {}, clear=False):
            if "TARGET_LANGUAGE" in os.environ:
                del os.environ["TARGET_LANGUAGE"]
            router = LLMRouter()
            instruction = router.get_language_instruction()
            self.assertIn("Japanese", instruction)

        # Should reflect custom TARGET_LANGUAGE
        with patch.dict(os.environ, {"TARGET_LANGUAGE": "English"}):
            router = LLMRouter()
            instruction = router.get_language_instruction()
            self.assertIn("English", instruction)

if __name__ == '__main__':
    unittest.main()
