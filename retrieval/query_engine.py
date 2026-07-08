import functools
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.documents import Document

from core.config import Config
from core.llm_router import LLMLayer
from core.prompts import get_query_prompt
from core.utils import WIKI_LINK_RE, safe_get_content

logger = logging.getLogger(__name__)


class WikiQueryEngine:
    """
    Wikiの知識を検索し、関連リンクを辿ってコンテキストを拡張した上で、
    LLMに回答を生成させるエンジン。
    """

    def __init__(self, qdrant_store, router, wiki_dir: Optional[Path] = None):
        """
        Args:
            qdrant_store: QdrantHybridStore のインスタンス
            router: LLMRouter のインスタンス
            wiki_dir (Path): Wikiファイルが保存されているディレクトリ
        """
        self.qdrant_store = qdrant_store
        self.router = router
        self.wiki_dir = wiki_dir if wiki_dir else Config.WIKI_DIR

    @functools.cached_property
    def _wiki_index(self) -> Dict[str, Path]:
        """
        Wikiディレクトリ内のMarkdownファイルをスキャンし、ファイル名をキーにしたインデックスを作成する。
        cached_property を使用することで、インスタンスごとに1度だけ実行される。
        重複がある場合は、concepts などの優先度が高いディレクトリのものを優先する。
        """
        import os
        index = {}
        try:
            def get_priority(p: Path) -> int:
                parts = p.parts
                if "concepts" in parts:
                    return 3
                elif "raw_markdown" in parts:
                    return 1
                return 2

            # rglob("*.md") より os.walk の方が大規模ディレクトリでは高速な傾向にある
            for root, _, files in os.walk(self.wiki_dir):
                for file in files:
                    if file.endswith(".md"):
                        path = Path(root) / file
                        stem = path.stem
                        if stem not in index:
                            index[stem] = path
                        else:
                            if get_priority(path) > get_priority(index[stem]):
                                index[stem] = path
        except Exception as e:
            logger.warning(f"Error indexing wiki directory {self.wiki_dir}: {e}")
        return index

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

        # 追跡対象のリンクを収集（実在するファイルのみ）
        # メインスレッドでパスを解決することで、インデックス構築時のロック競合を回避し、
        # 存在しないファイルに対する無駄なスレッド生成を抑制する。
        links_to_fetch = {}
        for d in initial_docs:
            if d.metadata.get("type") in ["wiki_page", "Concept", "Article", "Source", "Reference", "Landscape"]:
                # リンクの抽出 (Markdownエスケープを考慮)
                content = d.page_content.replace("\\", "")
                links = WIKI_LINK_RE.findall(content)
                for link in links:
                    if link not in seen_sources and link not in links_to_fetch:
                        link_path = self._find_link_path(link)
                        if link_path:
                            links_to_fetch[link] = link_path

        # 並列でリンク先コンテンツを取得
        if links_to_fetch:
            with ThreadPoolExecutor() as executor:
                # すでにパスは解決済みなので、直接パスを渡して読み込む
                future_to_link = {
                    executor.submit(self._read_link_content, link, path): link
                    for link, path in links_to_fetch.items()
                }
                for future in as_completed(future_to_link):
                    doc = future.result()
                    if doc:
                        all_context_docs.append(doc)
                        seen_sources.add(future_to_link[future])

        # 3. コンテキストの構造化
        context = self._build_context_string(all_context_docs)

        # 4. LLMによる回答生成
        llm = self.router.get_model(LLMLayer.L2)
        lang_inst = self.router.get_language_instruction()

        prompt = self._build_prompt(query_text, context, lang_inst)
        response = llm.invoke(prompt)

        return safe_get_content(response.content)

    def _read_link_content(self, link: str, link_path: Path) -> Optional[Document]:
        """
        リンク先のコンテンツを読み込み、Documentオブジェクトとして返す。
        """
        try:
            logger.info(f"リンク追跡: [[{link}]] ({link_path}) を追加の文脈として読み込みます。")
            linked_content = link_path.read_text(encoding="utf-8")
            return Document(
                page_content=linked_content,
                metadata={"source": link, "type": "explicit_link"}
            )
        except Exception as e:
            logger.error(f"Error reading linked file {link_path}: {e}")
        return None

    def _find_link_path(self, link: str) -> Optional[Path]:
        """
        指定されたリンク名に対応するMarkdownファイルをWikiディレクトリ内で検索する。
        キャッシュされたインデックスを使用する。
        """
        return self._wiki_index.get(link)

    def _build_context_string(self, docs: List[Document]) -> str:
        context_parts = []
        for d in docs:
            dtype = d.metadata.get("type", "unknown")
            source = d.metadata.get("source", "unknown")
            if dtype == "wiki_page":
                prefix = "📄 [Wiki Page]"
            elif dtype == "explicit_link":
                prefix = "🔗 [Linked Context]"
            else:
                prefix = "一次情報 [Raw Source]"
            context_parts.append(f"{prefix} Source: {source}\n{d.page_content}")

        return "\n\n---\n\n".join(context_parts)

    def _build_prompt(self, query: str, context: str, lang_inst: str) -> list:
        return get_query_prompt(query, context, lang_inst)
