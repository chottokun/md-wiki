import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from core.config import Config
from core.schemas import WikiFrontmatterSchema, DraftConfig
from core.utils import normalize_term, parse_frontmatter, dump_frontmatter, find_red_links

logger = logging.getLogger(__name__)

# タグ抽出用の正規表現 (Obsidianの仕様に準拠)
# 前に空白または行頭があり、#の後に1文字以上の英数字・スラッシュ・ハイフンが続くもの
TAG_PATTERN = re.compile(r'(?<!\S)#([\w/-]+)')

class ObsidianWriter:
    def __init__(self, wiki_dir: Optional[str] = None, staged_dir: Optional[str] = None):
        self.wiki_dir = Path(wiki_dir).resolve() if wiki_dir else Config.WIKI_DIR.resolve()
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        # Staged dir defaults to _staged relative to the workspace root if not provided
        self.staged_dir = Path(staged_dir).resolve() if staged_dir else Path("_staged").resolve()
        self.staged_dir.mkdir(parents=True, exist_ok=True)

    def approve_update(self, page_name: str) -> bool:
        """
        承認されたドラフトを本番のWikiディレクトリに反映し、レビューファイルを削除する。
        """
        logger.info(f"Approving update for: {page_name}")
        try:
            safe_page_name = normalize_term(page_name)
            staged_path = self.staged_dir / f"{safe_page_name}_review.md"
            wiki_path = self.wiki_dir / f"{safe_page_name}.md"

            if not staged_path.exists():
                logger.error(f"承認対象のファイルが見つかりません: {staged_path}")
                return False

            content = staged_path.read_text(encoding="utf-8")

            # Robust content extraction:
            # 1. Try to find content between '## Proposed Full Content' and a boundary (--- or ## Agent Metadata)
            match = re.search(r"## Proposed Full Content\n+(.*?)(?=\n---|\n## Agent Metadata|$)", content, re.DOTALL)
            if match:
                final_content = match.group(1).strip()
            else:
                # 2. If not found, take everything before the first boundary
                match = re.search(r"(.*?)(?=\n---|\n## Agent Metadata|$)", content, re.DOTALL)
                if match:
                    final_content = match.group(1).strip()
                else:
                    final_content = content.strip()

            # Wikiファイルを更新
            wiki_path.write_text(final_content, encoding="utf-8")

            # レビュー用一時ファイルを削除（クリーンアップ）
            staged_path.unlink()
            logger.info(f"Wikiを更新しました: {wiki_path}")
            return True
        except Exception as e:
            logger.error(f"Wikiの更新反映中にエラーが発生しました: {str(e)}")
            return False

    def _get_safe_path(self, base_dir: Path, *path_parts: str) -> Path:
        """ベースディレクトリ配下の安全なパスを生成し、ディレクトリトラバーサルを防止する。"""
        # 絶対パスが渡された場合にパスの起点がリセットされるのを防ぐため、
        # 各パーツから先頭のスラッシュを除去する
        safe_parts = [str(Path(p)).lstrip(os.sep).lstrip('/') for p in path_parts if p]

        # 結合して絶対パスに変換
        joined = base_dir.joinpath(*safe_parts).resolve()

        try:
            # joined が base_dir 配下にあることを確認
            joined.relative_to(base_dir)
        except ValueError:
            logger.error(f"Path traversal attempt blocked: {path_parts} under {base_dir}")
            raise ValueError(f"Security Alert: Invalid path components {path_parts}")

        return joined

    def generate_diff(self, old_text: str, new_text: str) -> str:
        """単純な行ベースの差分を生成（difflibを使用）"""
        import difflib
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
        return "\n".join(list(diff)[2:]) # ヘッダーを除去

    def create_draft_file(self, config: DraftConfig) -> Path:
        """
        レビュー用のファイルを wiki/ (または sub_dir) に作成する。
        """
        safe_page_name = normalize_term(config.page_name)

        # ディレクトリトラバーサル対策
        if config.sub_dir:
            target_dir = self._get_safe_path(self.wiki_dir, config.sub_dir)
        else:
            target_dir = self.wiki_dir

        target_dir.mkdir(parents=True, exist_ok=True)

        filename = safe_page_name if safe_page_name.endswith(".md") else f"{safe_page_name}.md"
        wiki_path = self._get_safe_path(target_dir, filename)
        
        source_link = self._handle_source_file(config.source_filename, config.source_path) if config.source_filename else None
        raw_link = self._handle_raw_markdown(safe_page_name, config.raw_markdown) if config.raw_markdown else None

        existing_data = None
        original_body = ""
        is_update = wiki_path.exists()
        if is_update:
            existing_data, original_body = parse_frontmatter(wiki_path.read_text(encoding="utf-8"))

        # 新しいコンテンツのパース
        proposed_data, proposed_body = parse_frontmatter(config.proposed_content)
        
        # クレンジング
        proposed_body = re.sub(r'^```(?:markdown|md)?\s*\n', '', proposed_body.strip())
        proposed_body = re.sub(r'\n```\s*$', '', proposed_body.strip())

        # メタデータのマージ
        base_data = existing_data if existing_data else {}
        if proposed_data:
            for key in ["tags", "sources", "aliases", "concepts"]:
                p_val = proposed_data.get(key, [])
                if isinstance(p_val, str):
                    p_val = [p_val]
                e_val = base_data.get(key, [])
                if isinstance(e_val, str):
                    e_val = [e_val]
                combined = list(set([v for v in (e_val + p_val) if v]))
                if combined:
                    base_data[key] = combined
            
            for key, val in proposed_data.items():
                if key not in ["tags", "sources", "aliases", "concepts", "created", "updated"]:
                    base_data[key] = val

        merged_data = self._prepare_metadata(base_data, source_link, raw_link, config.page_name, sub_dir=config.sub_dir)
        logger.info(f"FINAL MERGED TAGS: {merged_data.get('tags')}")
        
        diff_text = self.generate_diff(original_body, proposed_body) if is_update else ""
        diff_section = f"\n> [!caution] AIによる更新提案 (Merge Diff)\n> 既存の記述と新しい情報を比較し、変更箇所を抽出しました。必要に応じて人間が統合してください。\n> ```diff\n{diff_text}\n> ```\n" if (is_update and diff_text) else ""

        final_fm = dump_frontmatter(merged_data)
        footer = self._generate_footer(source_link, raw_link)
        
        body_content = proposed_body.strip()
        if not body_content.startswith("# "):
            body_content = f"# {config.page_name}\n\n{body_content}"
        
        final_content = f"{final_fm}\n\n{diff_section}\n{body_content}\n{footer}"
        wiki_path.write_text(final_content.strip(), encoding="utf-8")
        
        logger.info(f"Draft created/updated: {wiki_path}")
        return wiki_path

    def _prepare_metadata(self, base_data: Dict[str, Any], source_link: Optional[str], raw_link: Optional[str], page_name: Optional[str] = None, sub_dir: Optional[str] = None) -> Dict[str, Any]:
        """最終的なYAMLメタデータを構築し、Pydanticスキーマで厳密に管理する。"""
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
        
        # 既存/新規データを統合
        merged_dict = base_data.copy()
        
        # リンク情報の統合
        sources = merged_dict.get("sources", [])
        if source_link:
            sources.append(source_link)
        merged_dict["sources"] = sorted(list(set(sources)))

        # スキーマによるバリデーションとデフォルト値適用
        try:
            # Pydantic スキーマでパース & 正規化
            fm = WikiFrontmatterSchema.model_validate(merged_dict)
            
            # 日付とタイプの強制設定
            if not fm.created:
                fm.created = now_str
            fm.timestamp = now_str
            
            # type の動的判定
            if not fm.type or fm.type in ["wiki", "Article", "Concept"]:
                if sub_dir == "concepts":
                    fm.type = "Concept"
                elif sub_dir == "raw_markdown":
                    fm.type = "RawSource"
                elif sub_dir == "sources":
                    fm.type = "Source"
                elif sub_dir == "references":
                    fm.type = "Reference"
                elif not fm.type or fm.type == "wiki":
                    fm.type = "Article"
            
            # タグとエイリアス内の特殊ハイフン (ノンブレイキングハイフンなど) を標準ハイフンにクレンジング
            fm.tags = [t.replace('\u2011', '-').replace('\u2010', '-').replace('\uFF0D', '-').strip() for t in fm.tags]
            fm.tags = [t for t in fm.tags if t]
            
            fm.aliases = [a.replace('\u2011', '-').replace('\u2010', '-').replace('\uFF0D', '-').strip() for a in fm.aliases]
            fm.aliases = [a for a in fm.aliases if a]

            # concepts 内の特殊ハイフンも標準ハイフンにクレンジングし重複排除
            fm.concepts = [c.replace('\u2011', '-').replace('\u2010', '-').replace('\uFF0D', '-').strip() for c in fm.concepts]
            fm.concepts = sorted(list(set([c for c in fm.concepts if c])))

            # エイリアスが空の場合、ページ名から年度サフィックスや括弧を除外した自動エイリアスを提案
            if not fm.aliases and page_name:
                cleaned_alias = re.sub(r'_\d{4}$', '', page_name)
                cleaned_alias = re.sub(r'（.*?）$', '', cleaned_alias)
                cleaned_alias = re.sub(r'\(.*?\)$', '', cleaned_alias)
                if cleaned_alias != page_name:
                    fm.aliases.append(cleaned_alias)

            # 必須タグの保証
            if "未審査" not in fm.tags:
                fm.tags.append("未審査")
            fm.tags = sorted(list(set(fm.tags)))
            fm.aliases = sorted(list(set(fm.aliases)))

            # 要約（description）のクレンジング：ブロックコールのマークアップや太字記号を除去してプレーンテキストにする
            if fm.description:
                cleaned = fm.description
                cleaned = re.sub(r'>\s*\[!abstract\]\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'>\s*要約\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'^>\s*', '', cleaned, flags=re.MULTILINE)
                cleaned = cleaned.replace('**', '').replace('__', '')
                cleaned = cleaned.strip()
                fm.description = cleaned

            return fm.model_dump(exclude_none=True)
        except Exception as e:
            logger.error(f"Metadata validation error: {e}")
            # フォールバック: 辞書型で継続（ただし警告）
            merged_dict["updated"] = now_str
            return merged_dict

    def create_draft_from_schema(self, data: Dict[str, Any], sub_dir: Optional[str] = None) -> Path:
        page_name = data.get("title", "Untitled")
        proposed_body = data.get("body", "")
        nested_data, clean_body = parse_frontmatter(proposed_body)
        
        metadata = {
            "tags": list(set(data.get("tags", []) + (nested_data.get("tags", []) if nested_data else []))),
            "aliases": list(set(data.get("aliases", []) + (nested_data.get("aliases", []) if nested_data else []))),
            "concepts": list(set(data.get("concepts", []) + (nested_data.get("concepts", []) if nested_data else []))),
            "sources": list(set(data.get("sources", []) + (nested_data.get("sources", []) if nested_data else []))),
            "description": data.get("description", data.get("abstract", "")),
            "type": data.get("type") or (nested_data.get("type") if nested_data else None) or ("Concept" if sub_dir == "concepts" else ("RawSource" if sub_dir == "raw_markdown" else "Article"))
        }
        
        # LLMが誤って生成した # タイトル や > [!abstract] コールアウトを本文から削除
        clean_body = re.sub(r'^#\s+.*?\n+', '', clean_body, count=1).strip()
        clean_body = re.sub(r'^>\s*\[!abstract\].*?(?:\n>.*)*\n+', '', clean_body, flags=re.MULTILINE | re.IGNORECASE).strip()
        
        concepts_str = "\n".join([f"- {c}" for c in data.get("concepts", [])])
        
        final_body = f"""# {page_name}

> [!abstract] 要約
> {data.get('description', data.get('abstract', ''))}

{clean_body}

## 💡 主要な概念
{concepts_str}
"""
        full_content = f"{dump_frontmatter(metadata)}\n\n{final_body.strip()}"
        config = DraftConfig(
            page_name=page_name,
            proposed_content=full_content,
            source_filename=data.get("source_filename"),
            source_path=data.get("source_path"),
            raw_markdown=data.get("raw_markdown"),
            sub_dir=sub_dir
        )
        return self.create_draft_file(config)

    def _handle_source_file(
        self, filename: Optional[str], source_path: Optional[str] = None
    ) -> Optional[str]:
        if not filename:
            return None
        sources_dir = self._get_safe_path(self.wiki_dir, "sources")
        sources_dir.mkdir(exist_ok=True)
        
        # 出力先パスの検証
        target_path = self._get_safe_path(sources_dir, filename)

        # 入力ソースパスの決定
        if source_path:
            src = Path(source_path).resolve()
        else:
            # _raw ディレクトリを探す
            raw_base = Path("_raw").resolve()
            src = raw_base / Path(filename).name

        if not src.exists():
            # 相対パスでの検索も試行
            src = Path(filename).resolve()

        logger.info(f"  [File] Attempting to copy source: {src} -> {target_path}")
            
        if src.exists() and src.is_file():
            try:
                shutil.copy2(src, target_path)
                logger.info("  [File] Successfully copied source file.")
            except Exception as e:
                logger.error(f"  [File] Failed to copy source file: {e}")
        else:
            logger.warning(f"  [File] Source file not found: {src}")

        rel_path = target_path.relative_to(self.wiki_dir).as_posix()
        return f"[[{rel_path}]]"

    def _handle_raw_markdown(self, name: str, content: Optional[str]) -> Optional[str]:
        if not content:
            return None
        raw_dir = self._get_safe_path(self.wiki_dir, "raw_markdown")
        raw_dir.mkdir(exist_ok=True)

        filename = f"{name}.md" if not name.endswith(".md") else name
        raw_path = self._get_safe_path(raw_dir, filename)

        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
        fm_data = {
            "type": "RawSource",
            "title": f"Raw Source of {name}",
            "description": f"Raw parsed markdown content for {name}",
            "timestamp": now_str,
            "tags": ["raw-source"]
        }
        fm_str = dump_frontmatter(fm_data)
        full_content = f"{fm_str}\n{content}"

        raw_path.write_text(full_content, encoding="utf-8")
        rel_path = raw_path.relative_to(self.wiki_dir).as_posix()
        return f"[[{rel_path}]]"

    def _generate_footer(self, source_link: Optional[str], raw_link: Optional[str]) -> str:
        """OKF §8 準拠の Citations セクションを生成する。"""
        footer = "\n\n# Citations\n"
        if source_link:
            footer += f"- 一次資料: {source_link}\n"
        if raw_link:
            footer += f"- 解析済みテキスト: {raw_link}\n"
        return footer

    def page_exists(self, page_name: str) -> bool:
        """指定されたページ名がWiki内に存在するか確認する。"""
        safe_name = normalize_term(page_name)
        filename = f"{safe_name}.md"
        return (self.wiki_dir / filename).exists()

    def read_page(self, page_name: str) -> Optional[str]:
        """指定されたページの内容を読み込む。"""
        safe_name = normalize_term(page_name)
        filename = f"{safe_name}.md"
        wiki_path = self.wiki_dir / filename
        if wiki_path.exists():
            return wiki_path.read_text(encoding="utf-8")
        return None

    def add_log_entry(self, activity_type: str, details: str):
        """OKF §7 準拠の log.md にエントリを追加する。
        
        日付グループ方式: 同一日のエントリはまとめる。
        フォーマット: ## YYYY-MM-DD + * **Action**: description
        """
        log_path = self.wiki_dir / "log.md"
        today_str = datetime.now().strftime("%Y-%m-%d")
        # アクション名の先頭を大文字に
        action = activity_type.capitalize()
        new_entry = f"* **{action}**: {details}\n"
        
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8")
            today_heading = f"## {today_str}"
            if today_heading in content:
                # 同一日のセクションがある場合、その直後に追加
                content = content.replace(today_heading + "\n", today_heading + "\n" + new_entry, 1)
            else:
                # 新しい日付セクションを先頭に追加（ヘッダーの直後）
                header_end = content.find("\n") + 1 if content.startswith("# ") else 0
                header = content[:header_end]
                rest = content[header_end:].lstrip("\n")
                content = f"{header}\n{today_heading}\n{new_entry}\n{rest}"
            log_path.write_text(content.strip() + "\n", encoding="utf-8")
            # 新規作成
            content = f"# Directory Update Log\n\n## {today_str}\n{new_entry}"
            log_path.write_text(content, encoding="utf-8")

    def update_index(self):
        """OKF §6 準拠の index.md を自動生成する。
        
        - フロントマターなし（§6 準拠）
        - 標準 Markdown リンクを使用（OKF 標準、選択肢A）
        - 各エントリに description を付加
        - サブディレクトリにも index.md を自動生成
        """
        # 予約ファイル名と除外ディレクトリ
        reserved_files = {"index.md", "log.md"}
        
        # サブディレクトリの収集
        subdirs = sorted([d for d in self.wiki_dir.iterdir() 
                         if d.is_dir() and not d.name.startswith(".")])
        
        # ルート直下の概念ページ収集
        root_pages = sorted([p for p in self.wiki_dir.glob("*.md")
                            if p.name not in reserved_files])
        
        # --- ルート index.md の生成 ---
        sections = ["# md-wiki Knowledge Bundle"]
        
        # サブディレクトリセクション
        if subdirs:
            sections.append("\n# Subdirectories\n")
            for d in subdirs:
                # サブディレクトリ内のページ数をカウント
                md_count = len(list(d.rglob("*.md"))) - len(list(d.glob("index.md")))
                sections.append(f"* [{d.name}]({d.name}/index.md) - {md_count} concepts")
        
        # ルート直下のページ
        if root_pages:
            sections.append("\n# Articles\n")
            for p in root_pages:
                try:
                    desc = self._get_description(p)
                    sections.append(f"* [{p.stem}]({p.name}) - {desc}")
                except (PermissionError, FileNotFoundError, OSError) as e:
                    logger.error(f"Error reading {p} for index: {e}")
                    # Skip files that cannot be read
                    continue
        
        index_content = "\n".join(sections)
        (self.wiki_dir / "index.md").write_text(index_content.strip() + "\n", encoding="utf-8")
        
        # --- サブディレクトリの index.md 生成 ---
        for d in subdirs:
            self._generate_subdir_index(d)
    
    def _get_description(self, file_path: Path) -> str:
        """ファイルの frontmatter から description を取得する。"""
        # ファイルの読み込み自体でエラー（PermissionError等）が発生した場合は、呼び出し元で処理するために伝播させる
        content = file_path.read_text(encoding="utf-8")
        try:
            data, _ = parse_frontmatter(content)
            if data:
                desc = data.get("description", data.get("abstract", ""))
                if desc:
                    # 1行に切り詰め（80文字以内）
                    first_line = desc.split("\n")[0].strip()
                    return first_line[:80] + "..." if len(first_line) > 80 else first_line
        except Exception:
            pass
        return ""
    
    def _generate_subdir_index(self, dir_path: Path):
        """OKF §6 準拠のサブディレクトリ index.md を生成する。"""
        reserved_files = {"index.md", "log.md", "Management Dashboard.md"}
        pages = sorted([p for p in dir_path.glob("*.md") if p.name not in reserved_files])
        sub_dirs = sorted([d for d in dir_path.iterdir() if d.is_dir() and not d.name.startswith(".")])
        
        dir_name = dir_path.name.capitalize()
        sections = [f"# {dir_name}"]
        
        if sub_dirs:
            sections.append("")
            for sd in sub_dirs:
                sections.append(f"* [{sd.name}]({sd.name}/index.md)")
        
        if pages:
            sections.append("")
            for p in pages:
                try:
                    desc = self._get_description(p)
                    entry = f"* [{p.stem}]({p.name})"
                    if desc:
                        entry += f" - {desc}"
                    sections.append(entry)
                except (PermissionError, FileNotFoundError, OSError) as e:
                    logger.error(f"Error reading {p} for subdir index: {e}")
                    continue
        
        index_content = "\n".join(sections)
        (dir_path / "index.md").write_text(index_content.strip() + "\n", encoding="utf-8")

    def update_management_dashboard(self):
        """
        Wikiの状態を俯瞰できる管理ダッシュボード (Management Dashboard.md) を生成・更新する。
        """
        all_pages = list(self.wiki_dir.rglob("*.md"))
        # raw_markdown, sources, .obsidian, およびダッシュボード自身を除外
        pages = [
            p for p in all_pages
            if "raw_markdown" not in p.parts
            and "sources" not in p.parts
            and ".obsidian" not in p.parts
            and p.name != "Management Dashboard.md"
        ]

        pending_reviews = []
        red_links_counter = find_red_links(self.wiki_dir)

        for p in pages:
            try:
                content = p.read_text(encoding="utf-8")
                # 未審査タグのチェック (フロントマターまたは本文中)
                if "#未審査" in content or "未審査" in content:
                    # frontmatterを厳密にチェック
                    data, _ = parse_frontmatter(content)
                    if data and "未審査" in data.get("tags", []):
                        pending_reviews.append(p.stem)
                    elif "#未審査" in content:
                        pending_reviews.append(p.stem)
            except Exception as e:
                logger.error(f"Error processing {p} for dashboard: {e}")

        # ダッシュボードの構築
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sections = [
            "# 📋 Management Dashboard",
            f"\n最終更新: {now_str}\n",
            "---",
            "\n## 🔍 審査待ちページ (Pending Reviews)",
            "以下のページはAIによって生成され、まだ人間による確認が終わっていません。"
        ]

        if pending_reviews:
            for p_name in sorted(list(set(pending_reviews))):
                sections.append(f"- [[{p_name}]]")
        else:
            sections.append("- ✅ 審査待ちのページはありません。")

        sections.append("\n## 🚩 要作成概念 (Top Red-links)")
        sections.append(f"現在、合計 **{len(red_links_counter)}** 個の未作成概念が参照されています。")
        sections.append("以下は言及頻度が高い順のトップ20です（`main.py --lint` を実行すると、これらを優先して自動生成します）。")

        if red_links_counter:
            for term, count in red_links_counter.most_common(20):
                sections.append(f"- [[{term}]] ({count} 回の言及)")
        else:
            sections.append("- ✅ 不足している概念はありません。")

        sections.append("\n## 📊 システムステータス (System Status)")
        sections.append(f"- 総有効ページ数: {len(pages)}")
        sections.append(f"- 最終更新日時: {now_str}")
        sections.append(f"- 審査待ち率: {len(pending_reviews) / len(pages) * 100:.1f}%" if pages else "- 審査待ち率: 0%")

        dashboard_content = "\n".join(sections)
        dashboard_path = self.wiki_dir / "Management Dashboard.md"
        dashboard_path.write_text(dashboard_content.strip() + "\n", encoding="utf-8")
        logger.info(f"Dashboard updated: {dashboard_path}")
