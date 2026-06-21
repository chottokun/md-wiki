import subprocess
import os
import sys
from pathlib import Path

from core.utils import setup_windows_utf8

# Windowsのコンソールコードページを UTF-8 に設定
setup_windows_utf8()


def auto_rebuild():
    """
    RAG-Wiki システム全体をクリーン・リセットし、最新の設定でナレッジベースを再構築する。
    
    このスクリプトが実行する手順:
    1. Qdrant ベクトルデータベースのコレクション ('rag_wiki') を完全削除。
    2. wiki/ ディレクトリ内の既存 Markdown ファイルをリセット (Home.md, log.md, sources/ は保護)。
    3. wiki/raw_markdown/ ディレクトリ内の抽出済みテキストをクリア。
    4. Ollama コンテナを再起動し、GPUリソースをクリーンな状態にする。
    5. _raw/ ディレクトリ内の全 PDF を、自動承認モード (-y) で順次インジェスト。
    
    用途:
    - LLMモデルの変更（例: ローカルからクラウドAPIへの移行）後の再構築。
    - 執筆プロンプトやチャンク設定の大幅な変更の反映。
    - システムの整合性が失われた際の緊急復旧。
    """
    raw_dir = Path('_raw')
    wiki_dir = Path('wiki')
    pdfs = sorted(list(raw_dir.glob('*.pdf'))) # 順序を一定にするためソート
    
    print("\n--- 🚨 緊急リセット: QdrantおよびWikiファイルを初期化中 ---")
    
    # 1. Qdrantのリセット
    # インラインスクリプトでコレクションを削除
    subprocess.run([
        sys.executable, "-c", 
        "from retrieval.qdrant_store import QdrantHybridStore; store=QdrantHybridStore(); store.delete_collection(); store.close()"
    ], check=True)
    
    # 2. Wiki Markdownファイルのリセット（concepts等のサブディレクトリも対象）
    print("既存のWikiページを削除中...")
    for p in wiki_dir.rglob("*.md"):
        if p.name not in ["Home.md", "log.md"] and "raw_markdown" not in str(p) and "sources" not in str(p):
            p.unlink()
    
    # 3. 生Markdown抽出データとソースファイルの法のリセット
    raw_md_dir = wiki_dir / "raw_markdown"
    if raw_md_dir.exists():
        print("抽出済みRaw Markdownデータをクリア中...")
        for p in raw_md_dir.glob("*.md"):
            p.unlink()

    sources_dir = wiki_dir / "sources"
    if sources_dir.exists():
        print("コピー済みソースファイルをクリア中...")
        for p in sources_dir.glob("*"):
            if p.is_file() and p.name != ".gitkeep":
                p.unlink()
    
    # 4. インフラとリポジトリの確認
    mode = os.getenv("QDRANT_MODE", "local")
    print(f"現在のモード: {mode}")

    # Ollamaコンテナの再起動 (ローカルモード時のみ)
    if mode == "local":
        print("Ollamaコンテナを再起動中...")
        try:
            subprocess.run(["docker", "restart", "ollama"], check=True, capture_output=True)
        except Exception as e:
            print(f"  ⚠ Warning: Ollamaの再起動に失敗しました (Dockerが未設定の可能性があります): {e}")
    
    if not (wiki_dir / ".git").exists():
        print("WikiディレクトリをGitリポジトリとして初期化中...")
        subprocess.run(["git", "init", str(wiki_dir)], check=True)
        # 初期コミットが必要な場合のために作成
        (wiki_dir / ".gitkeep").touch()
        subprocess.run(["git", "-C", str(wiki_dir), "add", ".gitkeep"], check=True)
        subprocess.run(["git", "-C", str(wiki_dir), "commit", "-m", "Initial commit"], check=True)
    
    print(f"\n再構築対象のPDFを {len(pdfs)} 件検出しました。")

    
    # 5. バッチ・インジェストの実行
    for pdf in pdfs:
        print(f"\n🚀 再構成プロセス開始: {pdf.name}")
        # インジェストを実行（ドラフトと未審査タグの作成）
        subprocess.run(["uv", "run", "python", "main.py", str(pdf), "--yes"], check=True)
    
    print("\n🔄 Qdrantインデックスを同期中...")
    # 未審査タグがあっても強制的にインデックス化する
    subprocess.run(["uv", "run", "python", "main.py", "--sync", "--force"], check=True)
    
    print("\n🛠️ Wikiの健康診断（Red-linkの自動起票・conceptsページの再構築）を実行中...")
    subprocess.run([sys.executable, "main.py", "--lint", "--yes"], check=True)

    print("\n📊 管理ダッシュボードを更新中...")
    subprocess.run([
        sys.executable, "-c",
        "from output.obsidian_writer import ObsidianWriter; ObsidianWriter().update_management_dashboard()"
    ], check=True)

    print("\n" + "="*50)
    print("✅ 全データのドラフト再構築が完了しました。")
    print("   - Wiki内に '#未審査' タグ付きで全ページが生成されました。")
    print("   - Obsidianで内容を確認後、タグを削除して `main.py --sync` を実行してください。")
    print("="*50 + "\n")

if __name__ == "__main__":
    try:
        auto_rebuild()
    except Exception as e:
        print(f"\n❌ 再構築中に致命的なエラーが発生しました: {e}")
