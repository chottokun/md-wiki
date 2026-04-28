import sys
import uuid
import logging
import argparse
import subprocess
import os
from pathlib import Path
from typing import Dict, Any

if sys.platform == "win32":
    # 標準出力と標準エラーを UTF-8 に強制
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from agent.graph import app, qdrant_store
from core.llm_router import router, LLMLayer
from langgraph.types import Command

# ロギング構成
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag-wiki")
logger.setLevel(logging.INFO)

def run_git_commit(message: str):
    """
    Wikiディレクトリ（独立リポジトリ）に対して変更をステージングし、コミットする。
    
    Args:
        message (str): コミットメッセージ。
    """
    try:
        wiki_dir = "wiki"
        # 変更のステージング
        subprocess.run(["git", "add", "."], check=True, capture_output=True, cwd=wiki_dir)
        # 変更がある場合のみコミットを実行（--quietフラグで変更なし時は終了コード1を返す）
        result = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True, cwd=wiki_dir)
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True, cwd=wiki_dir)
            print(f"Commit: {message}")
    except Exception as e:
        logger.error(f"Wikiへの自動コミットに失敗しました: {e}")

def run_workflow(input_data: Dict[str, Any], auto_approve: bool = False):
    """
    LangGraphワークフローを起動し、必要に応じて人間によるレビューを介在させる。
    
    Args:
        input_data (Dict[str, Any]): 初期状態として渡すデータ。
        auto_approve (bool): Trueの場合、人間によるレビューをスキップして自動承認する。
    """
    # 実行セッションを識別するためのユニークなスレッドID
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n[Workflow] Starting...")

    current_state = None
    # ワークフローのストリーミング実行
    for event in app.stream(input_data, config, stream_mode="values"):
        current_state = event
        status = event.get("status")
        if status:
            print(f"  [進捗]: {status}")

    print("Done: Workflow finished.")
    if current_state and "target_page" in current_state:
        from output.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter()
        writer.update_index()
        log_type = "maintenance" if "maintenance_topic" in input_data else "ingest"
        writer.add_log_entry(log_type, f"Drafted {current_state['target_page']}")
        run_git_commit(f"Auto-draft: {current_state['target_page']}")
        print(f"Info: Check [[{current_state['target_page']}]] in Obsidian and edit/remove tags.")

import re

def run_query(query: str):
    """
    Wikiの知識（整理済みページ + 一次情報）を横断検索し、さらにリンク関係を辿って回答を生成する。
    """
    print(f"\n[Search] Searching knowledge base for: '{query}'")
    # 1. Qdrantから関連チャンクを取得
    initial_docs = qdrant_store.search(query, k=8)
    
    # 2. ヒットしたWikiページから [[リンク]] を抽出し、未取得の関連情報を能動的に取得
    all_context_docs = list(initial_docs)
    seen_sources = {d.metadata.get("source") for d in initial_docs}
    
    wiki_dir = Path("wiki")
    for d in initial_docs:
        if d.metadata.get("type") == "wiki_page":
            # リンクの抽出 (Markdownエスケープを考慮)
            content = d.page_content.replace("\\", "")
            links = re.findall(r"\[\[(.*?)\]\]", content)
            for link in links:
                if link not in seen_sources:
                    link_path = wiki_dir / f"{link}.md"
                    if link_path.exists():
                        logger.info(f"リンク追跡: [[{link}]] を追加の文脈として読み込みます。")
                        linked_content = link_path.read_text(encoding="utf-8")
                        from langchain_core.documents import Document
                        all_context_docs.append(Document(
                            page_content=linked_content,
                            metadata={"source": link, "type": "explicit_link"}
                        ))
                        seen_sources.add(link)
    
    # AIが情報の性質を理解できるようコンテキストを構造化
    context_parts = []
    for d in all_context_docs:
        dtype = d.metadata.get("type", "unknown")
        source = d.metadata.get("source", "unknown")
        if dtype == "wiki_page": prefix = "📄 [Wiki Page]"
        elif dtype == "explicit_link": prefix = "🔗 [Linked Context]"
        else: prefix = "一次情報 [Raw Source]"
        context_parts.append(f"{prefix} Source: {source}\n{d.page_content}")
    
    context = "\n\n---\n\n".join(context_parts)
    
    # LLMの取得と言語指示の生成
    llm = router.get_model(LLMLayer.L2)
    lang_inst = router.get_language_instruction()
    
    prompt = f"""あなたはWikiのナレッジアシスタントです。{lang_inst}
以下のWikiページ（整理済み）、関連リンク（自動追跡）、および一次情報（生データ）を参考にして、質問に答えてください。

## コンテキスト
{context}

## 質問: {query}

## 指示:
- {lang_inst}
- Wikiページや関連リンクに概要がある場合はそれを活用し、細かい事実は一次情報から補完してください。
- 根拠となった情報の出典を必ず [[ページ名]] または [[sources/PDF名]] 形式で明記してください。
- 外部の知識は絶対に混ぜないでください。

回答:"""

    response = llm.invoke(prompt)
    
    # 質問への回答活動をログに記録
    from output.obsidian_writer import ObsidianWriter
    ObsidianWriter().add_log_entry("query", f"Answered: {query[:30]}...")
    
    print("\n" + "="*50 + "\n" + response.content + "\n" + "="*50 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG-Wiki 統合CLI")
    parser.add_argument("input", nargs="?", help="ファイルパス（インジェスト時）またはトピック名（クエリ/メンテナンス時）")
    parser.add_argument("--query", "-q", action="store_true", help="クエリ（質問回答）モードを実行")
    parser.add_argument("--maintenance", "-m", action="store_true", help="メンテナンス（景観要約）モードを実行")
    parser.add_argument("--lint", "-l", action="store_true", help="Wikiの健康診断（リンク切れ・風化チェック）を実行")
    parser.add_argument("--sync", "-s", action="store_true", help="Wikiファイルを正としてQdrantを再構築（同期）する")
    parser.add_argument("--refine", "-r", action="store_true", help="手動編集したWikiページをAIエディターで洗練させる")
    parser.add_argument("--yes", "-y", action="store_true", help="確認プロンプトをスキップして自動承認する")
    parser.add_argument("--force", "-f", action="store_true", help="未審査タグを無視して同期する")
    parser.add_argument("--dry-run", action="store_true", help="ファイルへの書き込みを行わず、変更内容をログに出力する")
    
    args = parser.parse_args()
    
    # モードに応じたエントリーポイントの選択
    if args.query:
        if not args.input:
            print("質問内容を入力してください。")
        else:
            run_query(args.input)
    elif args.refine:
        if not args.input:
            print("洗練対象のWikiページ名（またはファイルパス）を入力してください。")
        else:
            from retrieval.sync_manager import GitSyncManager
            mgr = GitSyncManager(qdrant_store)
            filename = args.input if args.input.endswith(".md") else f"{args.input}.md"
            full_path = Path("wiki") / filename
            
            if not full_path.exists():
                print(f"Error: {full_path} does not exist.")
            else:
                content = full_path.read_text(encoding="utf-8")
                if "<<<<<<<" in content:
                    print("🚨 衝突マーカーを検知しました。コンフリクト解決モードで開始します。")
                    run_workflow({
                        "status": "starting_conflict",
                        "target_page": full_path.stem,
                        "raw_markdown": content
                    }, auto_approve=args.yes)
                else:
                    # git diff を取得するために、wikiリポジトリ内での相対パスを渡す
                    # full_path.name だけだとサブディレクトリに対応できないため、
                    # wiki/ からの相対パスを計算する
                    rel_path = full_path.relative_to(Path("wiki"))
                    diff = mgr.get_unstaged_diff(str(rel_path))
                    
                    # 差分がない場合、または新規ファイルの場合は、ファイル全体を対象にする
                    if not diff:
                        logger.info("未コミットの差分が見つからないため、ファイル全体を対象に洗練を実行します。")
                        diff = content

                    run_workflow({
                        "status": "starting_refine",
                        "target_page": full_path.stem,
                        "raw_markdown": diff
                    }, auto_approve=args.yes)
    elif args.sync:
        print("\n[Sync] Synchronizing Qdrant index and Git...")
        print("Note: Files with '#未審査' tag will be skipped.")
        from retrieval.sync_manager import GitSyncManager
        sync_mgr = GitSyncManager(qdrant_store)
        sync_mgr.perform_incremental_sync(include_unreviewed=args.force)
        from output.obsidian_writer import ObsidianWriter
        ObsidianWriter().add_log_entry("sync", "Performed incremental synchronization.")
        run_git_commit("Auto-sync: User triggered manual sync.")
        print("Done: Synchronization complete.")
    elif args.lint:
        run_workflow({"status": "starting_lint", "dry_run": args.dry_run})
    elif args.maintenance:
        if not args.input:
            print("統合対象のトピック名を入力してください。")
        else:
            run_workflow({"maintenance_topic": args.input}, auto_approve=args.yes)
    elif args.input:
        run_workflow({"input_file": args.input}, auto_approve=args.yes)
    else:
        parser.print_help()
