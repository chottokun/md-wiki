import shutil
import os
from pathlib import Path

def reset_env():
    """
    Wikiフォルダ内とQdrantデータをすべて削除し、クリーンな状態に戻します。
    """
    print("=== 環境のリセットを開始します ===")

    # 1. Wikiディレクトリのクリーンアップ
    wiki_dir = Path("wiki")
    if wiki_dir.exists():
        print(f"  - {wiki_dir} 内のファイルを削除中...")
        for item in wiki_dir.glob("*"):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        # .gitkeepを再作成
        (wiki_dir / ".gitkeep").touch()
        # サブディレクトリも再作成 (構造維持)
        (wiki_dir / "sources").mkdir(exist_ok=True)
        (wiki_dir / "raw_markdown").mkdir(exist_ok=True)
        (wiki_dir / "sources" / ".gitkeep").touch()
        (wiki_dir / "raw_markdown" / ".gitkeep").touch()

    # 2. Qdrantデータの削除
    qdrant_dir = Path("qdrant_data")
    if qdrant_dir.exists():
        print(f"  - {qdrant_dir} を削除中...")
        try:
            shutil.rmtree(qdrant_dir)
        except Exception as e:
            print(f"  Warning: Qdrantデータの削除中にエラーが発生しました（使用中の可能性があります）: {e}")

    print("\nReset complete.")

if __name__ == "__main__":
    reset_env()
