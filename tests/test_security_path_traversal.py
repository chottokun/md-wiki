import pytest
from pathlib import Path
from output.obsidian_writer import ObsidianWriter
from core.schemas import DraftConfig
import os
import shutil

def test_path_traversal_fix():
    # テスト用の一時ディレクトリ設定
    test_wiki_dir = Path("test_wiki_security").absolute()
    if test_wiki_dir.exists():
        shutil.rmtree(test_wiki_dir)
    test_wiki_dir.mkdir()

    writer = ObsidianWriter(wiki_dir=str(test_wiki_dir))
    
    # 悪意のあるパス
    malicious_sub_dir = "../evil_dir"
    page_name = "pwned"
    
    evil_path = test_wiki_dir.parent / "evil_dir"
    if evil_path.exists():
        shutil.rmtree(evil_path)

    try:
        # 修正後はここで ValueError が発生するはず
        path = writer.create_draft_file(DraftConfig(page_name=page_name, proposed_content="content", sub_dir=malicious_sub_dir))
        
        # もし例外が発生せずにここに来たら、まだ脆弱
        if evil_path.exists():
            print("VULNERABILITY STILL PRESENT: Directory created outside wiki_dir!")
            return False
        else:
            print("UNEXPECTED SUCCESS: No error, but file not created outside (maybe standard path?)")
            return False
            
    except ValueError as e:
        print(f"SUCCESS: Blocked by security as expected: {e}")
        return True
    except Exception as e:
        print(f"FAILED: Unexpected exception: {e}")
        return False
    finally:
        # クリーンアップ
        if test_wiki_dir.exists():
            shutil.rmtree(test_wiki_dir)
        if evil_path.exists():
            shutil.rmtree(evil_path)

if __name__ == "__main__":
    import sys
    success = test_path_traversal_fix()
    if not success:
        sys.exit(1)
