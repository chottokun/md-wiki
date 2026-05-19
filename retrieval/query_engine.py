from __future__ import annotations
import re
import logging
from pathlib import Path
from langchain_core.documents import Document
from core.llm_router import LLMLayer
from core.config import Config
from core.prompts import get_query_prompt
from core.utils import WIKI_LINK_RE

logger = logging.getLogger(__name__)

class WikiQueryEngine:
    """
    Wikiの知識を検索し、関連リンクを辿ってコンテキストを拡張した上で、
    LLMに回答を生成させるエンジン。
    """

    def __init__(self, qdrant_store, router, wiki_dir: Path | None = None):
        """
        Args:
            qdrant_store: QdrantHybridStore のインスタンス
            router: LLMRouter のインスタンス
            wiki_dir (Path): Wikiファイルが保存されているディレクトリ
        """
        self.qdrant_store = qdrant_store
        self.router = router
        self.wiki_dir = wiki_dir if wiki_dir else Config.WIKI_DIR

    def query(self, query_text: str, k: int = 8) -> str:
        """
        クエリに対してRAGプロセスを実行し、回答を返す。
        """
        logger.info(f"WikiQueryEngine: Searching for '{query_text}'")

        # 1. Qdrantから関連チャンクを取得
        initial_docs = self.qdrant_store.search(query_text, k=k)
        
        # 2. ヒットしたWikiページから [[リンク]] を抽出し、未取得の関連情報を能動的に取得
        all_context_docs = list(initial_docs)
        seen_sources = {d.metadata.get("source") for d in initial_docs}
        
        for d in initial_docs:
            if d.metadata.get("type") == "wiki_page":
                # リンクの抽出 (Markdownエスケープを考慮)
                content = d.page_content.replace("\\", "")
                links = WIKI_LINK_RE.findall(content)
                for link in links:
                    if link not in seen_sources:
                        link_path = self._find_link_path(link)
                        if link_path:
                            logger.info(f"リンク追跡: [[{link}]] ({link_path}) を追加の文脈として読み込みます。")
                            linked_content = link_path.read_text(encoding="utf-8")
                            all_context_docs.append(Document(
                                page_content=linked_content,
                                metadata={"source": link, "type": "explicit_link"}
                            ))
                            seen_sources.add(link)
        
        # 3. コンテキストの構造化
        context = self._build_context_string(all_context_docs)
        
        # 4. LLMによる回答生成
        llm = self.router.get_model(LLMLayer.L2)
        lang_inst = self.router.get_language_instruction()
        
        prompt = self._build_prompt(query_text, context, lang_inst)
        response = llm.invoke(prompt)
        
        return response.content

    def _find_link_path(self, link: str) -> Path | None:
        """
        指定されたリンク名に対応するMarkdownファイルをWikiディレクトリ内で検索する。
        サブディレクトリも再帰的に探索する。
        """
        # 1. 直下をまず探す (高速化のため)
        direct_path = self.wiki_dir / f"{link}.md"
        if direct_path.exists():
            return direct_path
        
        # 2. サブディレクトリを再帰的に探す
        # Windowsのケースインセンシティブな環境を考慮しつつ、rglobを使用
        try:
            for p in self.wiki_dir.rglob(f"{link}.md"):
                return p
        except Exception as e:
            logger.warning(f"Error searching for link [[{link}]]: {e}")
            
        return None

    def _build_context_string(self, docs: list[Document]) -> str:
        context_parts = []
        for d in docs:
            dtype = d.metadata.get("type", "unknown")
            source = d.metadata.get("source", "unknown")
            if dtype == "wiki_page": prefix = "📄 [Wiki Page]"
            elif dtype == "explicit_link": prefix = "🔗 [Linked Context]"
            else: prefix = "一次情報 [Raw Source]"
            context_parts.append(f"{prefix} Source: {source}\n{d.page_content}")
        
        return "\n\n---\n\n".join(context_parts)

    def _build_prompt(self, query: str, context: str, lang_inst: str) -> str:
        return get_query_prompt(query, context, lang_inst)
