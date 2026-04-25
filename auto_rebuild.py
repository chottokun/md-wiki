import subprocess
from pathlib import Path

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
        "uv", "run", "python", "-c", 
        "from retrieval.qdrant_store import QdrantHybridStore; QdrantHybridStore().delete_collection()"
    ], check=True)
    
    # 2. Wiki Markdownファイルのリセット
    print("既存のWikiページを削除中...")
    for p in wiki_dir.glob("*.md"):
        if p.name not in ["Home.md", "log.md"]:
            p.unlink()
    
    # 3. 生Markdown抽出データのリセット
    raw_md_dir = wiki_dir / "raw_markdown"
    if raw_md_dir.exists():
        print("抽出済みRaw Markdownデータをクリア中...")
        for p in raw_md_dir.glob("*.md"):
            p.unlink()
    
    # 4. Ollama のリフレッシュ
    print("Ollamaコンテナを再起動してGPUメモリを解放中...")
    subprocess.run(["docker", "restart", "ollama"], check=True)
    
    print(f"\n再構築対象のPDFを {len(pdfs)} 件検出しました。")
    
    # 5. バッチ・インジェストの実行
    for pdf in pdfs:
        print(f"\n🚀 再構成プロセス開始: {pdf.name}")
        # -y フラグにより、人間によるレビューをスキップして全自動で構築
        subprocess.run(["uv", "run", "python", "main.py", "-y", str(pdf)], check=True)
    
    print("\n" + "="*50)
    print("✅ 全データの再構築が完了しました。")
    print("   - ハイブリッド・インデックス (Raw + Wiki) 構築済み")
    print("   - タグ形式の修正適用済み")
    print("   - 原始資料 (PDF/Raw MD) リンク完了")
    print("="*50 + "\n")

if __name__ == "__main__":
    try:
        auto_rebuild()
    except Exception as e:
        print(f"\n❌ 再構築中に致命的なエラーが発生しました: {e}")
