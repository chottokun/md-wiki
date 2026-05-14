import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore, RetrievalMode, FastEmbedSparse
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models

# ロギング設定
logger = logging.getLogger(__name__)

class QdrantHybridStore:
    """
    Qdrantを使用したハイブリッド検索（Dense + Sparse）を提供する高機能ストア。
    """
    
    def __init__(
        self,
        collection_name: str = "rag_wiki",
    ):
        from dotenv import load_dotenv
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
            path = "./qdrant_data"
            logger.info(f"Qdrantをローカルモード({path})で初期化します。")
            self.client = QdrantClient(path=path)
        
        self.embeddings = OllamaEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "mxbai-embed-large"),
            base_url=os.getenv("LOCALLLM_BASE_URL", "http://localhost:11434")
        )
        self.sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

        self._ensure_collection()

        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
            sparse_embedding=self.sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(os.getenv("CHUNK_SIZE", "400")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "50")),
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

    def add_documents(self, documents: List[Document]):
        self.vector_store.add_documents(documents)

    def search(self, query: str, k: int = 5) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k)

    def sync_from_disk(self, include_unreviewed: bool = False, wiki_dir: Optional[str] = None, raw_md_dir: Optional[str] = None):
        """ディスク上の全Wikiファイルを再スキャンしてQdrantを再構築する。"""
        self.client.delete_collection(collection_name=self.collection_name)
        self._ensure_collection()
        
        # テスト等でディレクトリを明示的に指定された場合に対応
        w_dir = Path(wiki_dir) if wiki_dir else self.wiki_dir
        
        all_documents = []
        wiki_files = list(w_dir.glob("**/*.md"))
        for file_path in wiki_files:
            if any(x in file_path.name for x in [".md-wiki-sync-state", "Home.md", "log.md"]):
                continue
            
            content = file_path.read_text(encoding="utf-8")
            if not include_unreviewed:
                if "未審査" in content or "#未審査" in content:
                    continue
                
            source_name = file_path.stem
            is_raw = "raw_markdown" in str(file_path)
            
            if is_raw:
                pdf_name = source_name.replace("_raw", "") + ".pdf"
                all_documents.extend(self.get_chunks(content, {"source": pdf_name, "type": "raw_source"}))
            else:
                all_documents.extend(self.get_chunks(content, {"source": source_name, "type": "wiki_page"}))
        
        if all_documents:
            self.add_documents(all_documents)

        logger.info("全件同期が完了しました。")

    def delete_source(self, source_name: str):
        from qdrant_client.http import models as rest_models
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest_models.Filter(
                must=[
                    rest_models.FieldCondition(
                        key="metadata.source",
                        match=rest_models.MatchValue(value=source_name),
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
