from typing import Annotated, List, TypedDict, Optional
from langchain_core.documents import Document

def merge_list(left: list, right: list) -> list:
    """
    リストをマージするためのリデューサー関数。
    LangGraphのノード間でDocumentリストを蓄積するために使用される。
    """
    return left + right

class AgentState(TypedDict):
    """
    RAG-Wiki エージェントのワークフロー全体で共有・保持される状態の定義。
    
    各ノードはこの状態を読み取り、必要に応じて更新を行う。
    """
    
    # 処理対象の入力ファイルへのパス
    input_file: str
    
    # Doclingによってパースされた直後の生のMarkdownテキスト
    raw_markdown: Optional[str]
    
    # Qdrant検索や直接リンク追跡によって収集された関連ドキュメントのリスト
    # (リデューサーにより、ノードを通るたびに蓄積される)
    retrieved_docs: Annotated[List[Document], merge_list]
    
    # LLMによって生成された執筆案、または統合レポートの本文
    proposed_content: Optional[str]
    
    # 最終的な出力先となるWikiページの名前（拡張子なし）
    target_page: Optional[str]
    
    # ワークフローの現在の進捗状況（ingested, drafted, applied, error等）
    status: str
    
    # 人間によるレビュー結果 (approve / reject)
    feedback: Optional[str]
    
    # メンテナンス（Synthesis）モード実行時の対象トピック名
    maintenance_topic: Optional[str]
    
    # 元のPDF等のソースファイル名（wiki/sourcesへの保存とリンクに使用）
    source_filename: Optional[str]
