import os
import re
import yaml
import shutil
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from core.utils import normalize_term, parse_frontmatter, dump_frontmatter

from core.config import Config
from core.schemas import WikiFrontmatterSchema

logger = logging.getLogger(__name__)

# タグ抽出用の正規表現 (Obsidianのネストされたタグやハイフンも考慮)
TAG_PATTERN = re.compile(r'#[\w/-]+')

class ObsidianWriter:
    def __init__(self, wiki_dir: Optional[str] = None):
        self.wiki_dir = Path(wiki_dir) if wiki_dir else Config.WIKI_DIR
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

    def generate_diff(self, old_text: str, new_text: str) -> str:
        """単純な行ベースの差分を生成（difflibを使用）"""
        import difflib
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
        return "\n".join(list(diff)[2:]) # ヘッダーを除去

    def create_draft_file(self, page_name: str, proposed_content: str, 
                         source_filename: Optional[str] = None, 
                         source_path: Optional[str] = None,
                         raw_markdown: Optional[str] = None,
                         sub_dir: Optional[str] = None) -> Path:
        """
        レビュー用のファイルを wiki/ (または sub_dir) に作成する。
        """
        safe_page_name = normalize_term(page_name)
        target_dir = self.wiki_dir / sub_dir if sub_dir else self.wiki_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = safe_page_name if safe_page_name.endswith(".md") else f"{safe_page_name}.md"
        wiki_path = target_dir / filename
        
        source_link = self._handle_source_file(source_filename, source_path) if source_filename else None
        raw_link = self._handle_raw_markdown(safe_page_name, raw_markdown) if raw_markdown else None

        existing_data = None
        original_body = ""
        is_update = wiki_path.exists()
        if is_update:
            existing_data, original_body = parse_frontmatter(wiki_path.read_text(encoding="utf-8"))

        # 新しいコンテンツのパース
        proposed_data, proposed_body = parse_frontmatter(proposed_content)
        
        # クレンジング
        proposed_body = re.sub(r'^```(?:markdown|md)?\s*\n', '', proposed_body.strip())
        proposed_body = re.sub(r'\n```\s*$', '', proposed_body.strip())

        # メタデータのマージ
        base_data = existing_data if existing_data else {}
        if proposed_data:
            for key in ["tags", "sources", "aliases"]:
                p_val = proposed_data.get(key, [])
                if isinstance(p_val, str): p_val = [p_val]
                e_val = base_data.get(key, [])
                if isinstance(e_val, str): e_val = [e_val]
                combined = list(set([v for v in (e_val + p_val) if v]))
                if combined: base_data[key] = combined
            
            for key, val in proposed_data.items():
                if key not in ["tags", "sources", "aliases", "created", "updated"]:
                    base_data[key] = val

        merged_data = self._prepare_metadata(base_data, source_link, raw_link, page_name)
        logger.info(f"FINAL MERGED TAGS: {merged_data.get('tags')}")
        
        diff_text = self.generate_diff(original_body, proposed_body) if is_update else ""
        diff_section = f"\n> [!info] AIからの更新提案\n> ```diff\n{diff_text}\n> ```\n" if (is_update and diff_text) else ""

        final_fm = dump_frontmatter(merged_data)
        footer = self._generate_footer(source_link, raw_link)
        
        body_content = proposed_body.strip()
        if not body_content.startswith("# "):
            body_content = f"# {page_name}\n\n{body_content}"
        
        final_content = f"{final_fm}\n\n{diff_section}\n{body_content}\n{footer}"
        wiki_path.write_text(final_content.strip(), encoding="utf-8")
        
        logger.info(f"Draft created/updated: {wiki_path}")
        return wiki_path

    def _prepare_metadata(self, base_data: Dict[str, Any], source_link: Optional[str], raw_link: Optional[str], page_name: Optional[str] = None) -> Dict[str, Any]:
        """最終的なYAMLメタデータを構築し、Pydanticスキーマで厳密に管理する。"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 既存/新規データを統合
        merged_dict = base_data.copy()
        
        # リンク情報の統合
        sources = merged_dict.get("sources", [])
        if source_link: sources.append(source_link)
        merged_dict["sources"] = sorted(list(set(sources)))

        # スキーマによるバリデーションとデフォルト値適用
        try:
            # Pydantic スキーマでパース & 正規化
            fm = WikiFrontmatterSchema.model_validate(merged_dict)
            
            # 日付とタイプの強制設定
            if not fm.created: fm.created = now_str
            fm.updated = now_str
            fm.type = "wiki"
            
            # タグとエイリアス内の特殊ハイフン (ノンブレイキングハイフンなど) を標準ハイフンにクレンジング
            fm.tags = [t.replace('\u2011', '-').replace('\u2010', '-').replace('\uFF0D', '-').strip() for t in fm.tags]
            fm.tags = [t for t in fm.tags if t]
            
            fm.aliases = [a.replace('\u2011', '-').replace('\u2010', '-').replace('\uFF0D', '-').strip() for a in fm.aliases]
            fm.aliases = [a for a in fm.aliases if a]

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

            # 要約（abstract）のクレンジング：ブロックコールのマークアップや太字記号を除去してプレーンテキストにする
            if fm.abstract:
                cleaned = fm.abstract
                cleaned = re.sub(r'>\s*\[!abstract\]\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'>\s*要約\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r'^>\s*', '', cleaned, flags=re.MULTILINE)
                cleaned = cleaned.replace('**', '').replace('__', '')
                cleaned = cleaned.strip()
                fm.abstract = cleaned

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
            "sources": list(set(data.get("sources", []) + (nested_data.get("sources", []) if nested_data else []))),
            "abstract": data.get("abstract", "")
        }
        
        concepts_str = "\n".join([f"- {c}" for c in data.get("concepts", [])])
        final_body = f"""# {page_name}

> [!abstract] 要約
> {data.get('abstract', '')}

## 詳細解説
{clean_body}

## 💡 主要な概念
{concepts_str}
"""
        full_content = f"{dump_frontmatter(metadata)}\n\n{final_body}"
        return self.create_draft_file(
            page_name, 
            full_content, 
            source_filename=data.get("source_filename"),
            source_path=data.get("source_path"),
            raw_markdown=data.get("raw_markdown"),
            sub_dir=sub_dir
        )

    def _handle_source_file(self, filename: Optional[str], source_path: Optional[str] = None) -> Optional[str]:
        if not filename: return None
        sources_dir = self.wiki_dir / "sources"
        sources_dir.mkdir(exist_ok=True)
        
        # まず指定されたパス（source_path）を試す
        src = Path(source_path) if source_path else Path("_raw") / filename
        if not src.exists():
            # 見つからなければデフォルトの _raw を試す
            src = Path("_raw") / filename
            
        if src.exists():
            shutil.copy2(src, sources_dir / filename)
        return f"[[sources/{filename}]]"

    def _handle_raw_markdown(self, name: str, content: Optional[str]) -> Optional[str]:
        if not content: return None
        raw_dir = self.wiki_dir / "raw_markdown"
        raw_dir.mkdir(exist_ok=True)
        raw_path = raw_dir / f"{name}.md"
        raw_path.write_text(content, encoding="utf-8")
        return f"[[raw_markdown/{name}]]"

    def _generate_footer(self, source_link: Optional[str], raw_link: Optional[str]) -> str:
        footer = "\n\n---\n## 🔗 リソース\n"
        if source_link: footer += f"- **Original Source**: {source_link}\n"
        if raw_link: footer += f"- **Raw Markdown**: {raw_link}\n"
        return footer

    def add_log_entry(self, activity_type: str, details: str):
        log_path = self.wiki_dir / "log.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"## [{timestamp}] {activity_type} | {details}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def update_index(self):
        pages = sorted([p for p in self.wiki_dir.rglob("*.md")
                 if p.name not in ["Home.md", "log.md"] and "raw_markdown" not in str(p) and "sources" not in str(p)])

        page_list = []
        for p in pages:
            try:
                # ページを読み込み、タグ（#Tag_Name）を簡易抽出
                content = p.read_text(encoding="utf-8")
                # TAG_PATTERN を使用して効率的にタグを抽出
                tags = TAG_PATTERN.findall(content)
                tag_str = f" {' '.join(tags)}" if tags else ""
                page_list.append(f"- [[{p.stem}]]{tag_str}")
            except Exception as e:
                logger.error(f"Error reading {p} for index: {e}")
                page_list.append(f"- [[{p.stem}]]")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        index_md = f"# 🏠 RAG-Wiki Home\n\n## 📚 全ページ\n" + "\n".join(page_list) + f"\n\n---\n*Updated: {now_str}*"
        (self.wiki_dir / "Home.md").write_text(index_md, encoding="utf-8")
