import subprocess
import logging
import os
import re
from pathlib import Path
from typing import List, Tuple, Set
from retrieval.qdrant_store import QdrantHybridStore

logger = logging.getLogger(__name__)

class GitSyncManager:
    """
    Gitの変更履歴（コミット済みおよび未コミットの両方）に基づき、
    WikiファイルとQdrantインデックスの差分同期を管理する。
    """
    
    def __init__(self, store: QdrantHybridStore, wiki_dir: str = "wiki"):
        self.store = store
        self.wiki_dir = Path(wiki_dir).absolute()
        # 同期状態ファイル
        self.state_file = self.wiki_dir / ".md-wiki-sync-state"

    def _get_current_head(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"], 
                cwd=self.wiki_dir, capture_output=True, text=True
            )
            return res.stdout.strip()
        except:
            return "unknown"

    def _get_last_synced_hash(self) -> str:
        if self.state_file.exists():
            return self.state_file.read_text().strip()
        return ""

    def _save_sync_state(self, commit_hash: str):
        self.state_file.write_text(commit_hash)

    def get_changed_files(self) -> Set[Path]:
        """
        未コミットの変更、新規ファイル、および前回同期以降の変更ファイルを取得する。
        """
        changed_files = set()
        
        # 1. 未コミットの変更 (Staged + Unstaged)
        out_unstaged = subprocess.run(["git", "diff", "--name-only"], cwd=self.wiki_dir, capture_output=True, text=True).stdout
        out_staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.wiki_dir, capture_output=True, text=True).stdout
        
        # 2. 未追跡ファイル (Untracked)
        out_untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=self.wiki_dir, capture_output=True, text=True).stdout

        # 3. 前回同期以降の変更 (もしハッシュがあれば)
        last_hash = self._get_last_synced_hash()
        out_history = ""
        if last_hash and last_hash != "unknown":
            out_history = subprocess.run(["git", "diff", "--name-only", last_hash, "HEAD"], cwd=self.wiki_dir, capture_output=True, text=True).stdout

        for out in [out_unstaged, out_staged, out_untracked, out_history]:
            for line in out.splitlines():
                line = line.strip()
                if not line: continue
                
                # パスの解決
                # 実行ディレクトリ(wiki/など)からの相対パスか、リポジトリルートからのパスかが環境により異なる
                # ここでは柔軟に判定する
                if line.startswith("wiki/") or line.startswith("wiki\\"):
                    full_path = self.wiki_dir.parent / line
                else:
                    full_path = self.wiki_dir / line
                
                if full_path.suffix == ".md" and full_path.exists():
                    # 特殊ファイルは除外
                    if any(x in full_path.name for x in [".md-wiki-sync-state", "Home.md", "log.md"]):
                        continue
                    changed_files.add(full_path.resolve())
        
        return changed_files

    def perform_incremental_sync(self, include_unreviewed: bool = False):
        """
        差分同期を実行し、変更のあったファイルのみQdrantを更新する。
        include_unreviewed=False の場合、未審査タグがあるファイルはスキップする。
        """
        last_hash = self._get_last_synced_hash()
        if not last_hash or last_hash == "unknown":
            logger.warning("同期履歴が見つかりません。全件同期を実行します。")
            self.store.sync_from_disk(include_unreviewed=include_unreviewed)
            current_head = self._get_current_head()
            if current_head != "unknown":
                self._save_sync_state(current_head)
            return

        changed_files = self.get_changed_files()
        
        if not changed_files:
            logger.info("同期が必要な変更は見つかりませんでした。")
            return

        logger.info(f"{len(changed_files)} 件の変更を検出しました。同期を開始します。")
        
        for file_path in changed_files:
            # 未審査タグのチェック
            content = file_path.read_text(encoding="utf-8")
            if not include_unreviewed:
                if "未審査" in content or "#未審査" in content:
                    logger.info(f"  [Skip] {file_path.name} (未審査タグあり)")
                    continue

            # Qdrantへの登録
            source_name = file_path.stem
            # 既存の同一ソースを一旦削除（更新のため）
            self.store.delete_source(source_name)
            
            # メタデータの判定
            is_raw = "raw_markdown" in str(file_path)
            if is_raw:
                pdf_name = source_name.replace("_raw", "") + ".pdf"
                self.store.add_text(content, {"source": pdf_name, "type": "raw_source"})
            else:
                self.store.add_text(content, {"source": source_name, "type": "wiki_page"})
            
            logger.info(f"  [Sync] {file_path.name} を更新しました。")

        # 同期状態を更新
        current_head = self._get_current_head()
        if current_head != "unknown":
            self._save_sync_state(current_head)
            
        logger.info("差分同期が完了しました。")
    def get_unstaged_diff(self, file_path: str) -> str:
        """
        指定されたファイルの未コミットの差分を取得する。
        """
        try:
            # 1. まずはインデックス（staged）との差分を確認
            res = subprocess.run(
                ["git", "diff", "HEAD", file_path],
                cwd=self.wiki_dir, capture_output=True, text=True
            )
            diff = res.stdout.strip()
            if diff:
                return diff
            
            # 2. もし差分がない場合は、新規ファイル（Untracked）か確認
            # (Git管理下になければ diff は空になるため)
            res = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", file_path],
                cwd=self.wiki_dir, capture_output=True, text=True
            )
            if res.stdout.strip():
                # 新規ファイルの場合は内容をそのまま返す
                return Path(file_path).read_text(encoding="utf-8")
                
            return ""
        except Exception as e:
            logger.error(f"Error getting diff for {file_path}: {e}")
            return ""
