import os
import logging
from pathlib import Path
from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore, RetrievalMode, FastEmbedSparse
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models

# ロギング設定
logger = logging.getLogger(__name__)

class QdrantHybridStore:
    """
    Qdrantを使用したハイブリッド検索（Dense + Sparse）を提供する高機能ストア。
    
    機能:
    1. Dense Vector: Ollama (mxbai-embed-large等) を使用した意味検索。
    2. Sparse Vector: FastEmbed (BM25等) を使用したキーワード検索。
    3. 自動チャンク化: 環境変数設定に基づき、長文を意味的な区切りで分割して格納。
    4. ハイブリッド検索: DenseとSparseの結果を統合して高精度なリトリーバルを実現。
    """
    
    def __init__(
        self,
        collection_name: str = "rag_wiki",
        url: str = "http://localhost:6333",
    ):
        """
        Qdrantストアを初期化し、必要に応じてコレクションを作成する。
        
        Args:
            collection_name (str): Qdrant内のコレクション名。
            url (str): QdrantサーバーのURL。
        """
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)
        
        # Dense 埋め込みモデルの設定 (Ollama)
        self.embeddings = OllamaEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "mxbai-embed-large"),
            base_url=os.getenv("LOCALLLM_BASE_URL", "http://localhost:11434")
        )

        # Sparse 埋め込みモデルの設定 (FastEmbed)
        self.sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

        # コレクションが存在しない場合は自動作成
        if not self.client.collection_exists(self.collection_name):
            logger.info(f"Qdrantコレクションを新規作成します: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=rest_models.VectorParams(
                    size=1024, # mxbai-embed-large の出力次元
                    distance=rest_models.Distance.COSINE
                ),
                sparse_vectors_config={
                    "langchain-sparse": rest_models.SparseVectorParams() # LangChain互換の名前
                }
            )

        # ハイブリッド検索用の QdrantVectorStore インスタンス
        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
            sparse_embedding=self.sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
        )

    def add_text(self, text: str, metadata: Dict[str, Any]):
        """
        長いテキストを指定されたチャンクサイズに分割してQdrantに追加する。
        チャンク設定は環境変数 (CHUNK_SIZE, CHUNK_OVERLAP) から読み込む。
        
        Args:
            text (str): 保存する生のテキスト。
            metadata (Dict[str, Any]): 各チャンクに付与する共通メタデータ。
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
        
        # 意味的な区切り（。や改行）を尊重して分割
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "、", " ", ""]
        )
        
        chunks = text_splitter.split_text(text)
        documents = [Document(page_content=chunk, metadata=metadata) for chunk in chunks]
        
        self.add_documents(documents)

    def add_documents(self, documents: List[Document]):
        """
        LangChain Documentリストをそのままベクトルストアに追加する。
        
        Args:
            documents (List[Document]): 追加するドキュメント。
        """
        logger.info(f"{len(documents)} 件のドキュメントを Qdrant コレクション '{self.collection_name}' に追加中...")
        self.vector_store.add_documents(documents)

    def search(self, query: str, k: int = 5) -> List[Document]:
        """
        ハイブリッド検索（意味 + キーワード）を実行する。
        
        Args:
            query (str): 検索クエリ。
            k (int): 取得するドキュメント数。
            
        Returns:
            List[Document]: 検索結果。
        """
        logger.info(f"検索実行中: '{query}' (k={k})")
        return self.vector_store.similarity_search(query, k=k)

    def sync_from_disk(self, wiki_dir: str = "wiki", raw_md_dir: str = "wiki/raw_markdown"):
        """
        ディスク上のMDファイルを正として、Qdrantインデックスを完全に再構築する。
        """
        logger.info("Wikiファイルを正としてQdrantインデックスを再構築中...")
        self.delete_collection()
        # 再作成は初期化時に自動で行われる（あるいはここでも呼ぶ）
        self.__init__(collection_name=self.collection_name, url=self.client._client.rest_uri)
        
        # 1. 完成Wikiページの同期
        wiki_path = Path(wiki_dir)
        for p in wiki_path.glob("*.md"):
            if p.name not in ["Home.md", "log.md"]:
                content = p.read_text(encoding="utf-8")
                self.add_text(content, {"source": p.stem, "type": "wiki_page"})
                
        # 2. 原始資料 (Raw Markdown) の同期
        raw_path = Path(raw_md_dir)
        if raw_path.exists():
            for p in raw_path.glob("*.md"):
                content = p.read_text(encoding="utf-8")
                # 元のPDF名を推測（_rawを除去）
                source_name = p.stem.replace("_raw", "") + ".pdf"
                self.add_text(content, {"source": source_name, "type": "raw_source"})
        
        logger.info("Qdrantの再同期が完了しました。")

    def delete_collection(self):
        """
        コレクションを削除する（主にテスト・再構築用）。
        """
        logger.warning(f"コレクション {self.collection_name} を削除します。")
        self.client.delete_collection(self.collection_name)
