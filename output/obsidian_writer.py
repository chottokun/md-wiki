import difflib
import logging
from pathlib import Path
from typing import Optional, Dict, List

# ロギング設定
logger = logging.getLogger(__name__)

class ObsidianWriter:
    """
    Wikiの更新案を作成し、Obsidianでレビュー可能な形式で出力・管理するクラス。
    
    役割:
    1. 既存Wikiと新提案の差分（Unified Diff）を生成。
    2. Obsidianのコールアウト機能を用いたレビュー用ファイルの作成。
    3. 承認後のWiki反映とQdrant同期のトリガー。
    4. Git履歴を解析したナレッジ活動状況（Hot/Stale）の抽出。
    5. 全ページを統合するインデックス (Home.md) と活動記録 (log.md) の保守。
    """
    
    def __init__(self, wiki_dir: str = "wiki", staged_dir: str = "_staged"):
        """
        ObsidianWriterを初期化する。
        
        Args:
            wiki_dir (str): Wikiデータ（Obsidian Vault）のルートディレクトリ。
            staged_dir (str): レビュー待ちファイルを保存するディレクトリ。
        """
        self.wiki_dir = Path(wiki_dir)
        self.staged_dir = Path(staged_dir)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.staged_dir.mkdir(parents=True, exist_ok=True)

    def generate_diff(self, original: str, proposed: str) -> str:
        """
        2つのテキスト間の差分（Unified Diff形式）を生成する。
        
        Args:
            original (str): 既存のコンテンツ。
            proposed (str): 新しく提案されたコンテンツ。
            
        Returns:
            str: 生成された差分テキスト。
        """
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile="既存のWiki (Existing Wiki)",
            tofile="新提案 (Proposed Update)"
        )
        return "".join(diff)

    def create_review_file(self, page_name: str, proposed_content: str) -> Path:
        """
        レビュー用のファイルを _staged/ に作成する。
        既存ファイルがある場合は差分を含め、Obsidianのコールアウトで強調表示する。
        
        Args:
            page_name (str): 対象のWikiページ名。
            proposed_content (str): AIが生成した新コンテンツ案。
            
        Returns:
            Path: 生成されたレビューファイルのパス。
        """
        wiki_path = self.wiki_dir / f"{page_name}.md"
        staged_path = self.staged_dir / f"{page_name}_review.md"
        
        original_content = ""
        if wiki_path.exists():
            original_content = wiki_path.read_text(encoding="utf-8")

        diff_text = self.generate_diff(original_content, proposed_content)
        
        # レビュー用Markdownの構成
        review_md = f"""---
page: "{page_name}"
status: "pending_review"
---

# Wiki Update Review: {page_name}

> [!info] 提案された変更
> 以下の差分を確認してください。
> 承認する場合はCLI上で `a` を入力するか、`-y` フラグを使用してください。

## 差分 (Diff)
```diff
{diff_text if diff_text else "変更なし (新規作成ページ)"}
```

## Proposed Full Content
{proposed_content}

---
## Agent Metadata (Do not delete)
<!-- ID: {page_name} -->
"""
        staged_path.write_text(review_md, encoding="utf-8")
        logger.info(f"レビューファイルを作成しました: {staged_path}")
        return staged_path

    def approve_update(self, page_name: str) -> bool:
        """
        レビュー案を承認し、正式なWikiページとして反映する。
        
        Args:
            page_name (str): 承認対象のページ名。
            
        Returns:
            bool: 成功した場合はTrue。
        """
        staged_path = self.staged_dir / f"{page_name}_review.md"
        wiki_path = self.wiki_dir / f"{page_name}.md"
        
        if not staged_path.exists():
            logger.error(f"承認対象のレビューファイルが見つかりません: {staged_path}")
            return False

        try:
            content = staged_path.read_text(encoding="utf-8")
            
            # 本文のみを抽出するロジック
            parts = content.split("## Proposed Full Content\n")
            if len(parts) < 2:
                logger.error("レビューファイル内に提案内容が見つかりません。")
                return False
            
            # メタデータ識別子までを取得
            final_content = parts[1].split("\n---\n## Agent Metadata (Do not delete)")[0].strip()

            # 正式なWikiページとして保存
            wiki_path.write_text(final_content, encoding="utf-8")
            
            # レビュー用一時ファイルを削除（クリーンアップ）
            staged_path.unlink()
            logger.info(f"Wikiを更新しました: {wiki_path}")
            return True
        except Exception as e:
            logger.error(f"Wikiの更新反映中にエラーが発生しました: {str(e)}")
            return False

    def add_log_entry(self, activity_type: str, details: str):
        """
        時系列ログ (log.md) に新しいアクティビティを記録する。
        
        Args:
            activity_type (str): アクティビティの種類 (ingest, query, lint, maintenance)。
            details (str): 詳細内容。
        """
        from datetime import datetime
        log_path = self.wiki_dir / "log.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        entry = f"## [{timestamp}] {activity_type} | {details}\n"
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
        logger.info(f"活動をログに記録しました: {activity_type}")

    def get_page_activity(self) -> Dict[str, List[str]]:
        """
        Gitの履歴を解析し、最近活発なページ(Hot)と、長期間更新がないページ(Stale)を特定する。
        
        Returns:
            Dict[str, List[str]]: {"hot": [...], "stale": [...]}
        """
        import subprocess
        from collections import Counter
        activity = {"hot": [], "stale": []}
        
        try:
            # 1. 最近1ヶ月で更新頻度が高い上位5件を取得 (Hot)
            res = subprocess.run(
                ["git", "log", "--since='1 month ago'", "--name-only", "--pretty=format:"],
                cwd=self.wiki_dir, capture_output=True, text=True
            )
            files = [line.strip() for line in res.stdout.split("\n") 
                     if line.endswith(".md") and line not in ["Home.md", "log.md"]]
            hot_files = [f.replace(".md", "") for f, count in Counter(files).most_common(5)]
            activity["hot"] = hot_files

            # 2. 3ヶ月以上更新がない「放置された」ページを特定 (Stale)
            all_pages = {p.stem for p in self.wiki_dir.glob("*.md") 
                         if p.name not in ["Home.md", "log.md"]}
            res_recent = subprocess.run(
                ["git", "log", "--since='3 months ago'", "--name-only", "--pretty=format:"],
                cwd=self.wiki_dir, capture_output=True, text=True
            )
            recent_files = {line.strip().replace(".md", "") 
                            for line in res_recent.stdout.split("\n") if line.endswith(".md")}
            activity["stale"] = sorted(list(all_pages - recent_files))
            
        except Exception as e:
            logger.error(f"Git履歴の解析中にエラーが発生しました: {e}")
        return activity

    def update_index(self):
        """
        Wiki内の全ファイルをスキャンし、インデックスページ (Home.md) を自動再構成する。
        各ページのタグ情報を収集し、カテゴリ別に整理する。
        """
        pages = list(self.wiki_dir.glob("*.md"))
        pages = [p for p in pages if p.name not in ["Home.md", "log.md"]]
        
        tag_map = {}
        page_list = []
        
        for p in pages:
            try:
                # ページを読み込み、タグ（#Tag_Name）を簡易抽出
                content = p.read_text(encoding="utf-8")
                # リンクとして機能させるためスペースを考慮
                tags = [word for word in content.replace("\n", " ").split() 
                        if word.startswith("#") and len(word) > 1]
                
                page_list.append(f"- [[{p.stem}]]")
                for tag in tags:
                    tag_map.setdefault(tag, []).append(f"[[{p.stem}]]")
            except Exception:
                continue

        # タグセクションの生成
        tag_section_parts = []
        for tag in sorted(tag_map.keys()):
            p_list = sorted(list(set(tag_map[tag])))
            tag_section_parts.append(f"### {tag}\n" + "\n".join([f"- {p}" for p in p_list]))
        
        tag_section = "\n\n".join(tag_section_parts)
        
        # Home.md の構築
        index_md = f"""# 🏠 RAG-Wiki Home

## 📚 全ページ
{chr(10).join(sorted(page_list))}

## 🏷️ タグ別
{tag_section}

---
*Generated by RAG-Wiki Agent. Last updated: {Path(self.wiki_dir).stat().st_mtime}*
"""
        (self.wiki_dir / "Home.md").write_text(index_md, encoding="utf-8")
        logger.info("Wikiインデックス (Home.md) を更新しました。")
