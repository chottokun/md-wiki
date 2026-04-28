import os
from enum import Enum
from typing import Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()

class LLMLayer(Enum):
    """
    タスクの難易度に応じたLLMの階層定義。
    """
    L1 = "lightweight"    # 軽量：Doclingアノテーション、単純なタグ付け等
    L2 = "standard"       # 標準：Wikiマージ、差分生成、要約等
    L3 = "advanced"       # 高度：複雑な推論、矛盾検知、Landscape生成等

class LLMProvider(Enum):
    """
    サポートされているLLMプロバイダー。
    """
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    GEMINI = "gemini"

class LLMRouter:
    """
    環境変数とタスクレイヤーに基づいてLLMインスタンスを動的に生成・管理するファクトリ。
    
    役割:
    1. 環境変数 (.env) からのモデル設定読み込み。
    2. プロバイダー (Ollama / Sakura API等) の切り替え。
    3. タスク難易度 (L1-L3) に応じたモデルの選択。
    4. 多言語設定の適用。
    """
    
    def __init__(self):
        """初期化時に環境変数からプロバイダーとモデル名を読み込む。"""
        self.provider = LLMProvider(os.getenv("LLM_PROVIDER", "ollama"))
        self.local_model = os.getenv("LOCALLLM_MODEL", "gemma4:latest")
        self.standard_model = os.getenv("STANDARDLLM_MODEL", "gemma4:latest")
        self.advanced_model = os.getenv("OPENAI_COMPATIBLE_MODEL", "gpt-oss-120b")
        
    def get_model(self, layer: LLMLayer, **kwargs: Any) -> BaseChatModel:
        """
        指定されたレイヤーに最適なLLMモデルインスタンスを返却する。
        
        Args:
            layer (LLMLayer): 要求されるタスクの階層。
            **kwargs: LangChainクライアントに渡す追加の引数。
            
        Returns:
            BaseChatModel: 生成されたLLMインスタンス。
        """
        if self.provider == LLMProvider.OLLAMA:
            return self._get_ollama_model(layer, **kwargs)
        elif self.provider == LLMProvider.OPENAI_COMPATIBLE:
            return self._get_openai_compatible_model(layer, **kwargs)
        elif self.provider == LLMProvider.GEMINI:
            return self._get_gemini_model(layer, **kwargs)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _get_ollama_model(self, layer: LLMLayer, **kwargs: Any) -> ChatOllama:
        """Ollamaプロバイダーのモデルを取得。VRAM節約設定を自動付与する。"""
        model_map = {
            LLMLayer.L1: self.local_model,
            LLMLayer.L2: self.standard_model,
            LLMLayer.L3: self.standard_model,
        }
        
        # RTX 3060 12GB等の環境でモデルを動的に入れ替えるための設定
        base_kwargs = {
            "model": model_map[layer],
            "base_url": os.getenv("LOCALLLM_BASE_URL", "http://localhost:11434"),
            "keep_alive": "0" # 推論直後にVRAMを開放
        }
        base_kwargs.update(kwargs)
        return ChatOllama(**base_kwargs)

    def _get_openai_compatible_model(self, layer: LLMLayer, **kwargs: Any) -> ChatOpenAI:
        """OpenAI互換（さくらAI Engine等）プロバイダーのモデルを取得。"""
        # 現状、全レイヤーで最高品質のadvanced_model(120B等)を使用する設定
        base_kwargs = {
            "model": self.advanced_model,
            "openai_api_key": os.getenv("OPENAI_COMPATIBLE_API"),
            "openai_api_base": os.getenv("OPENAI_COMPATIBLE_BASE_URL"),
        }
        
        base_kwargs.update(kwargs)
        return ChatOpenAI(**base_kwargs)

    def _get_gemini_model(self, layer: LLMLayer, **kwargs: Any) -> BaseChatModel:
        """将来的なGemini API実装用のプレースホルダ。"""
        raise NotImplementedError(
            "Gemini API provider is not yet implemented. "
            "Please add 'langchain-google-genai' to pyproject.toml and configure keys."
        )

    def get_language_instruction(self) -> str:
        """
        環境変数に基づいて、生成結果の言語を強制するためのシステムプロンプト断片を生成する。
        
        Returns:
            str: 「必ず日本語で出力してください」等の指示文字列。
        """
        lang = os.getenv("TARGET_LANGUAGE", "Japanese")
        return f"必ず{lang}で回答・出力してください。"

# システム全体で共有するシングルトンインスタンス
router = LLMRouter()
