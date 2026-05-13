"""
Wiki再構築テスト。
ゼロからWikiを構築し、生成された記事の品質を検証する。

注意: このテストは実際のLLMを呼び出す統合テストです。
"""
import sys
import os
import shutil
import time
import subprocess
from pathlib import Path
from core.utils import parse_frontmatter

if sys.platform == "win32":
    # Windowsのコンソールコードページを UTF-8 (65001) に強制変更
    import ctypes
    import os
    try:
        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    # 環境変数でPythonサブプロセスにもUTF-8を強制
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    # 標準出力と標準エラーを UTF-8 に強制
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def run_cmd(cmd_list, timeout=120):
    """コマンドを実行し、完了を待つ。"""
    print(f"  Running: {' '.join(cmd_list)}")
    result = subprocess.run(
        cmd_list, capture_output=True, text=True,
        encoding="utf-8", errors='replace', timeout=timeout
    )
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            if 'INFO' in line or 'WARNING' in line or 'ERROR' in line:
                print(f"    {line.strip()}")
    if result.returncode != 0:
        print(f"  ⚠ Exit code {result.returncode}")
        if result.stderr:
            # 最後の10行だけ表示
            for line in result.stderr.strip().split('\n')[-10:]:
                print(f"    {line.strip()}")
    return result

def test_full_rebuild():
    """Wikiをゼロから再構築し、品質を検証する。"""
    wiki_dir = Path("wiki")
    qdrant_dir = Path("qdrant_data")
    
    # ── 1. 初期化 ──
    print("\n[1/5] Initializing Wiki...")
    if wiki_dir.exists():
        # .obsidian は保持する
        for item in wiki_dir.iterdir():
            if item.name == ".obsidian":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        wiki_dir.mkdir()
    
    (wiki_dir / "concepts").mkdir(exist_ok=True)
    (wiki_dir / "sources").mkdir(exist_ok=True)
    (wiki_dir / "raw_markdown").mkdir(exist_ok=True)
    (wiki_dir / "concepts" / ".gitkeep").touch()
    
    # Qdrant もリセット
    if qdrant_dir.exists():
        shutil.rmtree(qdrant_dir)
    
    # ── 2. データ投入 ──
    print("[2/5] Ingesting test document 1...")
    r1 = run_cmd(["uv", "run", "python", "main.py", "tests/data_a.md", "--yes"])
    
    # Qdrantロック回避のため少し待機
    time.sleep(3)
    
    print("[3/5] Ingesting test document 2...")
    r2 = run_cmd(["uv", "run", "python", "main.py", "tests/data_merge_test.md", "--yes"])
    
    time.sleep(3)
    
    # ── 3. Lint（自律拡張） ──
    print("[4/5] Running Lint for autonomous expansion...")
    run_cmd(["uv", "run", "python", "main.py", "--lint"])
    
    # ── 4. 品質検証 ──
    print("[5/5] Verifying output quality...\n")
    
    errors = []
    warnings = []
    
    # 4a. Home.md の存在確認
    if not (wiki_dir / "Home.md").exists():
        errors.append("Home.md が生成されていません")
    
    # 4b. Wiki 直下のページ確認
    wiki_pages = [p for p in wiki_dir.glob("*.md")
                  if p.name not in ("Home.md", "log.md")]
    
    print(f"  Wiki直下のページ: {[p.name for p in wiki_pages]}")
    
    if len(wiki_pages) == 0:
        errors.append("Wiki直下にページが1つも生成されていません")
    
    # 4c. 各ページの品質チェック
    for p in wiki_pages:
        content = p.read_text(encoding="utf-8")
        data, body = parse_frontmatter(content)
        
        page_name = p.stem
        print(f"\n  --- {page_name} ---")
        
        # YAML プロパティの検証
        if data is None:
            errors.append(f"  {page_name}: YAMLフロントマターがありません")
            continue
        
        tags = data.get("tags", [])
        print(f"    tags: {tags}")
        
        if "未審査" not in tags:
            errors.append(f"  {page_name}: '未審査' タグがありません")
        
        if len(tags) <= 1:
            warnings.append(f"  {page_name}: タグが '未審査' のみ（LLM提案タグが欠落）")
        
        # 内部リンクの検証
        links = re.findall(r"\[\[(.*?)\]\]", body)
        print(f"    内部リンク数: {len(links)}")
        if len(links) < 3:
            warnings.append(f"  {page_name}: 内部リンクが3つ未満 ({len(links)}個)")
        
        # [!abstract] の存在確認
        if "[!abstract]" not in content:
            warnings.append(f"  {page_name}: [!abstract] コールアウトがありません")
    
    # 4d. concepts/ ディレクトリの確認
    concepts = list((wiki_dir / "concepts").glob("*.md"))
    print(f"\n  概念ページ: {[c.name for c in concepts]}")
    if len(concepts) == 0:
        errors.append("概念ページが生成されていません（Red-linkが抽出・処理されていません）")

    # 4e. sources/ と raw_markdown/ の確認
    sources = list((wiki_dir / "sources").glob("*"))
    raw_mds = list((wiki_dir / "raw_markdown").glob("*.md"))
    print(f"\n  Sourceファイル数: {len(sources)}")
    print(f"  Raw Markdown数: {len(raw_mds)}")
    if len(sources) == 0:
        errors.append("wiki/sources にファイルが保存されていません")
    if len(raw_mds) == 0:
        errors.append("wiki/raw_markdown にファイルが保存されていません")
    
    # ── 結果表示 ──
    print("\n" + "="*50)
    if errors:
        print("❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
    if warnings:
        print("⚠ WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    if not errors and not warnings:
        print("✨ All checks passed!")
    elif not errors:
        print("✅ No critical errors (warnings only)")
    
    print("="*50)
    
    # エラーがある場合のみ失敗とする（警告は許容）
    assert len(errors) == 0, f"Critical errors found: {errors}"

import re

if __name__ == "__main__":
    test_full_rebuild()
