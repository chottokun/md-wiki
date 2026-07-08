import unittest
import os
from unittest.mock import patch
from core.llm_router import LLMRouter, LLMLayer, LLMProvider
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

class TestLLMRouterGetModel(unittest.TestCase):

    def test_ollama_provider_layers(self):
        env = {
            "LLM_PROVIDER": "ollama",
            "LOCALLLM_MODEL": "local-model",
            "STANDARDLLM_MODEL": "standard-model",
            "LOCALLLM_BASE_URL": "http://ollama:11434"
        }
        with patch.dict(os.environ, env):
            router = LLMRouter()

            # L1 Layer
            model_l1 = router.get_model(LLMLayer.L1)
            self.assertIsInstance(model_l1, ChatOllama)
            self.assertEqual(model_l1.model, "local-model")
            self.assertEqual(model_l1.base_url, "http://ollama:11434")
            self.assertEqual(model_l1.keep_alive, "0")

            # L2 Layer
            model_l2 = router.get_model(LLMLayer.L2)
            self.assertIsInstance(model_l2, ChatOllama)
            self.assertEqual(model_l2.model, "standard-model")
            self.assertEqual(model_l2.keep_alive, "0")

            # L3 Layer
            model_l3 = router.get_model(LLMLayer.L3)
            self.assertIsInstance(model_l3, ChatOllama)
            self.assertEqual(model_l3.model, "standard-model")
            self.assertEqual(model_l3.keep_alive, "0")

    def test_openai_compatible_provider(self):
        env = {
            "LLM_PROVIDER": "openai_compatible",
            "OPENAI_COMPATIBLE_MODEL": "advanced-model",
            "OPENAI_COMPATIBLE_API": "fake-key",
            "OPENAI_COMPATIBLE_BASE_URL": "https://api.openai.com/v1"
        }
        with patch.dict(os.environ, env):
            router = LLMRouter()

            for layer in LLMLayer:
                model = router.get_model(layer)
                self.assertIsInstance(model, ChatOpenAI)
                self.assertEqual(model.model_name, "advanced-model")
                self.assertEqual(str(model.openai_api_key.get_secret_value()), "fake-key")
                self.assertEqual(model.openai_api_base, "https://api.openai.com/v1")

    def test_gemini_provider_defaults(self):
        env = {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "gemini-key",
            "GEMINI_MODEL": ""
        }
        with patch.dict(os.environ, env):
            router = LLMRouter()

            # L1/L2 default
            model_l1 = router.get_model(LLMLayer.L1)
            self.assertIsInstance(model_l1, ChatGoogleGenerativeAI)
            self.assertEqual(model_l1.model, "gemini-1.5-flash")

            # L3 default
            model_l3 = router.get_model(LLMLayer.L3)
            self.assertIsInstance(model_l3, ChatGoogleGenerativeAI)
            self.assertEqual(model_l3.model, "gemini-1.5-pro")

    def test_gemini_provider_override_and_fallback_key(self):
        # We want to ensure GEMINI_API_KEY is not set to test fallback to GEMINI_API
        env = {
            "LLM_PROVIDER": "gemini",
            "GEMINI_MODEL": "gemini-custom",
            "GEMINI_API": "fallback-key"
        }
        # patch.dict can't easily remove keys without clearing everything or being messy.
        # But we can patch os.environ with a dict that doesn't have GEMINI_API_KEY and use clear=True
        # Or just patch it to an empty string which also triggers the 'or' fallback.
        env_with_empty_key = env.copy()
        env_with_empty_key["GEMINI_API_KEY"] = ""

        with patch.dict(os.environ, env_with_empty_key):
            router = LLMRouter()
            model = router.get_model(LLMLayer.L1)
            self.assertEqual(model.model, "gemini-custom")
            self.assertEqual(model.google_api_key.get_secret_value(), "fallback-key")

    def test_kwargs_passing(self):
        env = {
            "LLM_PROVIDER": "ollama",
            "LOCALLLM_MODEL": "local-model"
        }
        with patch.dict(os.environ, env):
            router = LLMRouter()
            # Test temperature passing for Ollama
            model = router.get_model(LLMLayer.L1, temperature=0.7)
            # langchain_ollama.ChatOllama uses temperature in its client or config
            self.assertEqual(model.temperature, 0.7)

        env = {
            "LLM_PROVIDER": "openai_compatible",
            "OPENAI_COMPATIBLE_MODEL": "advanced-model",
            "OPENAI_COMPATIBLE_API": "fake-key"
        }
        with patch.dict(os.environ, env):
            router = LLMRouter()
            model = router.get_model(LLMLayer.L1, temperature=0.3)
            self.assertEqual(model.temperature, 0.3)

    def test_unsupported_provider(self):
        router = LLMRouter()
        router.provider = "unsupported"
        with self.assertRaises(ValueError):
            router.get_model(LLMLayer.L1)

    def test_get_language_instruction(self):
        with patch.dict(os.environ, {"TARGET_LANGUAGE": "English"}):
            router = LLMRouter()
            instruction = router.get_language_instruction()
            self.assertIn("English", instruction)

        with patch.dict(os.environ, {"TARGET_LANGUAGE": "Japanese"}):
            router = LLMRouter()
            instruction = router.get_language_instruction()
            self.assertIn("Japanese", instruction)

if __name__ == '__main__':
    unittest.main()
