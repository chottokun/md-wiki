import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models
from core.config import Config
from core.utils import parse_frontmatter

# ロギング設定
logger = logging.getLogger(__name__)

class QdrantHybridStore:
    """
    Qdrantを使用したハイブリッド検索（Dense + Sparse）を提供する高機能ストア。
    """
    
    def __init__(
        self,
        collection_name: str = "rag_wiki",
        path: Optional[str] = None
    ):
        load_dotenv()
        self.collection_name = collection_name
        self.wiki_dir = Path("wiki")

        mode = os.getenv("QDRANT_MODE", "local")
        if mode == "server":
            url = os.getenv("QDRANT_URL", "http://localhost:6333")
            logger.info(f"Qdrantをサーバーモード({url})で初期化します。")
            self.client = QdrantClient(url=url)
        elif mode == "memory":
            logger.info("Qdrantをインメモリモードで初期化します。")
            self.client = QdrantClient(location=":memory:")
        else:
            q_path = path or os.getenv("QDRANT_PATH", "./qdrant_data")
            logger.info(f"Qdrantをローカルモード({q_path})で初期化します。")
            self.client = QdrantClient(path=q_path)

        
        import urllib.request
        ollama_running = False
        ollama_url = os.getenv("LOCALLLM_BASE_URL", "http://localhost:11434")
        if ollama_url.startswith(("http://", "https://")):
            try:
                with urllib.request.urlopen(ollama_url, timeout=1.0) as response:  # nosec B310
                    if response.status == 200:
                        ollama_running = True
            except Exception:  # nosec B110
                pass

        if ollama_running:
            logger.info("Ollama is running. Using OllamaEmbeddings.")
            self.embeddings = OllamaEmbeddings(
                model=os.getenv("EMBEDDING_MODEL", "mxbai-embed-large"),
                base_url=ollama_url
            )
        else:
            logger.info("Ollama is not running. Falling back to local FastEmbedEmbeddings with mixedbread-ai/mxbai-embed-large-v1.")
            from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
            self.embeddings = FastEmbedEmbeddings(
                model_name="mixedbread-ai/mxbai-embed-large-v1"
            )
        self.sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

        self._ensure_collection()

        if os.getenv("SKIP_SPARSE_EMBEDDINGS") == "true":
            retrieval_mode = RetrievalMode.DENSE
        else:
            retrieval_mode = RetrievalMode.HYBRID

        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
            sparse_embedding=self.sparse_embeddings,
            retrieval_mode=retrieval_mode,
        )
        
        try:
            chunk_size = int(os.getenv("CHUNK_SIZE", "400"))
            chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        except ValueError:
            logger.warning("Invalid CHUNK_SIZE or CHUNK_OVERLAP environment variable. Using defaults.")
            chunk_size = 400
            chunk_overlap = 50

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "、", " ", ""]
        )

    def _ensure_collection(self):
        """コレクションが存在しない場合は作成する。"""
        if not self.client.collection_exists(self.collection_name):
            logger.info(f"Qdrantコレクションを新規作成します: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=rest_models.VectorParams(
                    size=1024, # mxbai-embed-large
                    distance=rest_models.Distance.COSINE
                ),
                sparse_vectors_config={
                    "langchain-sparse": rest_models.SparseVectorParams()
                }
            )

    def get_chunks(self, text: str, metadata: Dict[str, Any]) -> List[Document]:
        chunks = self.text_splitter.split_text(text)
        return [Document(page_content=chunk, metadata=metadata) for chunk in chunks]

    def add_text(self, text: str, metadata: Dict[str, Any]):
        documents = self.get_chunks(text, metadata)
        self.add_documents(documents)

    def add_documents(self, documents: List[Document], batch_size: int = 100):
        """ドキュメントをバッチサイズごとに分割して登録する。"""
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            self.vector_store.add_documents(batch)

    def search(self, query: str, k: int = 5) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k)

    def sync_from_disk(self, include_unreviewed: Optional[bool] = None, wiki_dir: Optional[str] = None, raw_md_dir: Optional[str] = None):
        """ディスク上の全Wikiファイルを再スキャンしてQdrantを再構築する。"""
        if include_unreviewed is None:
            include_unreviewed = Config.INCLUDE_UNREVIEWED

        self.client.delete_collection(collection_name=self.collection_name)
        self._ensure_collection()
        
        # テスト等でディレクトリを明示的に指定された場合に対応
        w_dir = Path(wiki_dir) if wiki_dir else self.wiki_dir
        
        wiki_files = list(w_dir.glob("**/*.md"))

        def process_file(file_path: Path) -> List[Document]:
            if any(x in file_path.name for x in [".md-wiki-sync-state", "Home.md", "index.md", "log.md"]):
                return []
            
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return []

            if not include_unreviewed:
                if "未審査" in content or "#未審査" in content:
                    return []
                
            source_name = file_path.stem
            is_raw = "raw_markdown" in str(file_path)
            
            data, _ = parse_frontmatter(content)
            
            if is_raw:
                pdf_name = source_name.replace("_raw", "") + ".pdf"
                doc_type = data.get("type", "RawSource") if data else "RawSource"
                if doc_type == "raw_source":
                    doc_type = "RawSource"
                return self.get_chunks(content, {"source": pdf_name, "type": doc_type})
            else:
                doc_type = data.get("type", "Concept") if data else "Concept"
                if doc_type == "wiki_page" or doc_type == "wiki":
                    doc_type = "Article"
                return self.get_chunks(content, {"source": source_name, "type": doc_type})

        all_documents = []
        with ThreadPoolExecutor() as executor:
            results = executor.map(process_file, wiki_files)
            for doc_list in results:
                all_documents.extend(doc_list)
        
        if all_documents:
            self.add_documents(all_documents)

        logger.info("全件同期が完了しました。")

    def delete_source(self, source_name: str):
        self.delete_sources([source_name])

    def delete_sources(self, source_names: List[str]):
        """複数のソースをまとめて削除する。"""
        if not source_names:
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest_models.Filter(
                must=[
                    rest_models.FieldCondition(
                        key="metadata.source",
                        match=rest_models.MatchAny(any=source_names),
                    )
                ]
            ),
        )

    def delete_collection(self):
        self.client.delete_collection(self.collection_name)

    def close(self):
        """クライアント接続を明示的に閉じる。"""
        if hasattr(self, 'client'):
            self.client.close()
            logger.info("Qdrant client connection closed.")
