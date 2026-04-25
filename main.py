import sys
import uuid
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any
from agent.graph import app, qdrant_store
from core.llm_router import router, LLMLayer
from langgraph.types import Command

# ロギング構成
logging.basicConfig(level=logging.WARNING)
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
            print(f"📦 Wiki Git Commit: {message}")
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
    
    print(f"\n🚀 ワークフローを開始します...")

    current_state = None
    # ワークフローのストリーミング実行
    for event in app.stream(input_data, config, stream_mode="values"):
        current_state = event
        status = event.get("status")
        if status:
            print(f"  [進捗]: {status}")

    # 実行が停止（interrupt）しているか確認
    snapshot = app.get_state(config)
    if snapshot.next and "review" in snapshot.next[0]:
        if auto_approve:
            choice = 'a'
            print("\n🤖 自動承認モード (-y) で継続します...")
        else:
            print(f"\n📝 レビューが必要です。 _staged/ ディレクトリのファイルを確認してください。")
            choice = input("\nアクションを選択してください [a]承認(approve) / [r]却下(reject) / [q]終了(quit): ").lower()

        if choice == 'a':
            print("✅ 承認されました。Wikiへ反映中...")
            # Command(resume=...) を使って停止したノードを再開させる
            for event in app.stream(Command(resume="approve"), config, stream_mode="values"):
                current_state = event # 最終状態を更新
                print(f"  [進捗]: {event.get('status')}")
            
            # 反映後の後処理：インデックス更新、ログ記録、Gitコミット
            from output.obsidian_writer import ObsidianWriter
            writer = ObsidianWriter()
            writer.update_index()
            # メンテナンスモードとインジェストモードでログ種別を分ける
            log_type = "maintenance" if "maintenance_topic" in input_data else "ingest"
            writer.add_log_entry(log_type, f"Updated {current_state['target_page']}")
            run_git_commit(f"Auto-update: {current_state['target_page']}")
        else:
            print("操作はキャンセルされました。")

def run_query(query: str):
    """
    Wikiの知識（整理済みページ + 原始資料）を横断検索し、回答を生成する。
    
    Args:
        query (str): ユーザーからの質問。
    """
    print(f"\n🔍 ナレッジベースを検索中: '{query}'")
    # Qdrantから関連チャンクを取得
    docs = qdrant_store.search(query, k=8)
    
    # AIが情報の性質を理解できるようコンテキストを構造化
    context_parts = []
    for d in docs:
        dtype = d.metadata.get("type", "unknown")
        source = d.metadata.get("source", "unknown")
        prefix = "📄 [Wiki Page]" if dtype == "wiki_page" else "原始資料 [Raw Source]"
        context_parts.append(f"{prefix} Source: {source}\n{d.page_content}")
    
    context = "\n\n---\n\n".join(context_parts)
    
    # LLMの取得と言語指示の生成
    llm = router.get_model(LLMLayer.L2)
    lang_inst = router.get_language_instruction()
    
    prompt = f"""あなたはWikiのナレッジアシスタントです。{lang_inst}
以下のWikiページ（整理済み）と原始資料（生データ）を参考にして、質問に答えてください。

## コンテキスト
{context}

## 質問: {query}

## 指示:
- {lang_inst}
- Wikiページに概要がある場合はそれを活用し、細かい数値や事実は原始資料から補完してください。
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
    parser.add_argument("--yes", "-y", action="store_true", help="確認プロンプトをスキップして自動承認する")
    
    args = parser.parse_args()
    
    # モードに応じたエントリーポイントの選択
    if args.query:
        if not args.input:
            print("質問内容を入力してください。")
        else:
            run_query(args.input)
    elif args.lint:
        run_workflow({"status": "starting_lint"})
    elif args.maintenance:
        if not args.input:
            print("統合対象のトピック名を入力してください。")
        else:
            run_workflow({"maintenance_topic": args.input}, auto_approve=args.yes)
    elif args.input:
        run_workflow({"input_file": args.input}, auto_approve=args.yes)
    else:
        parser.print_help()
