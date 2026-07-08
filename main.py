import uuid
import logging
import argparse
import os
from typing import Dict, Any

from core.utils import setup_windows_utf8

# Windowsのコンソールコードページを UTF-8 に設定
setup_windows_utf8()

from agent.graph import app, get_qdrant_store
from core.llm_router import router
from retrieval.query_engine import WikiQueryEngine
from core.config import Config
from core.git_utils import run_git_commit

# キャッシュディレクトリの構成
os.environ.setdefault("HF_HOME", str(Config.MODELS_CACHE_DIR / "huggingface"))
os.environ.setdefault("FASTEMBED_CACHE_PATH", str(Config.MODELS_CACHE_DIR / "fastembed"))
Config.MODELS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ロギング構成
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag-wiki")
logger.setLevel(logging.INFO)

def run_workflow(input_data: Dict[str, Any], auto_approve: bool = False):
    """
    LangGraphワークフローを起動し、必要に応じて人間によるレビューを介在させる。
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print("\n[Workflow] Starting...")

    # 1. 最初の実行 (中断点まで)
    current_state = None
    for event in app.stream(input_data, config, stream_mode="values"):
        current_state = event
        status = event.get("status")
        if status:
            print(f"  [進捗]: {status}")

    # チェックポイントを確認し、中断されている場合は継続（auto_approve時）
    snapshot = app.get_state(config)
    if snapshot.next and "review" in snapshot.next:
        if auto_approve:
            print("  [承認]: 自動承認されたため、書き込みを実行します。")
            for event in app.stream(None, config, stream_mode="values"):
                current_state = event
        else:
            print(f"\n[待機]: レビュー待ちです。[[{current_state.get('target_page')}]] の内容を確認し、承認してください。")
            print("(--yes オプションで自動承認可能です)")

    print("Done: Workflow finished.")
    if current_state and "target_page" in current_state:
        from output.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter()
        writer.update_index()
        writer.update_management_dashboard()
        log_type = "maintenance" if "maintenance_topic" in input_data else "ingest"
        writer.add_log_entry(log_type, f"Drafted {current_state['target_page']}")
        run_git_commit(f"Auto-draft: {current_state['target_page']}")
        print(f"Info: Check [[{current_state['target_page']}]] in Obsidian and edit/remove tags.")

def run_query(query: str):
    """
    Wikiの知識（整理済みページ + 一次情報）を横断検索し、さらにリンク関係を辿って回答を生成する。
    """
    print(f"\n[Search] Searching knowledge base for: '{query}'")
    
    # WikiQueryEngine を使用して回答を生成
    store = get_qdrant_store()
    engine = WikiQueryEngine(store, router)
    answer = engine.query(query)
    
    # 質問への回答活動をログに記録
    from output.obsidian_writer import ObsidianWriter
    ObsidianWriter().add_log_entry("query", f"Answered: {query[:30]}...")
    
    print("\n" + "="*50 + "\n" + answer + "\n" + "="*50 + "\n")

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
    try:
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
                store = get_qdrant_store()
                mgr = GitSyncManager(store)
                filename = args.input if args.input.endswith(".md") else f"{args.input}.md"
                full_path = Config.WIKI_DIR / filename
                
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
                        rel_path = full_path.relative_to(Config.WIKI_DIR)
                        diff = mgr.get_unstaged_diff(str(rel_path))
                        
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
            store = get_qdrant_store()
            sync_mgr = GitSyncManager(store)
            sync_mgr.perform_incremental_sync(include_unreviewed=args.force)
            from output.obsidian_writer import ObsidianWriter
            writer = ObsidianWriter()
            writer.add_log_entry("sync", "Performed incremental synchronization.")
            writer.update_management_dashboard()
            run_git_commit("Auto-sync: User triggered manual sync.")
            print("Done: Synchronization complete.")
        elif args.lint:
            run_workflow({"status": "starting_lint", "dry_run": args.dry_run})
            from output.obsidian_writer import ObsidianWriter
            ObsidianWriter().update_management_dashboard()
        elif args.maintenance:
            if not args.input:
                print("統合対象のトピック名を入力してください。")
            else:
                run_workflow({"maintenance_topic": args.input}, auto_approve=args.yes)
        elif args.input:
            run_workflow({"input_file": args.input}, auto_approve=args.yes)
        else:
            parser.print_help()
    finally:
        from agent.graph import _qdrant_store
        if _qdrant_store is not None:
            _qdrant_store.close()
