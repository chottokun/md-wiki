import os
import sys
import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from core.utils import parse_frontmatter, dump_frontmatter
from core.schemas import WikiFrontmatterSchema

def setup_argparse():
    parser = argparse.ArgumentParser(description="Migrate md-wiki to OKF v0.1 format.")
    parser.add_argument("wiki_dir", nargs="?", default="wiki", help="Path to the wiki directory")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing to disk")
    parser.add_argument("--backup", action="store_true", help="Create a backup zip of the wiki folder before migrating")
    return parser.parse_args()

def backup_wiki(wiki_dir: Path):
    if not wiki_dir.exists():
        return
    backup_name = f"wiki_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.make_archive(backup_name, 'zip', wiki_dir)
    print(f"✅ Created backup archive: {backup_name}.zip")

def migrate_frontmatter_and_content(file_path: Path, wiki_root: Path, dry_run: bool):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return

    data, body = parse_frontmatter(content)
    if data is None:
        # No frontmatter, construct a default one
        data = {}

    # 1. Determine type based on directory path
    rel_parts = file_path.relative_to(wiki_root).parent.parts
    inferred_type = "Article"
    if "concepts" in rel_parts:
        inferred_type = "Concept"
    elif "raw_markdown" in rel_parts:
        inferred_type = "RawSource"
    elif "references" in rel_parts:
        inferred_type = "Reference"
    elif "sources" in rel_parts:
        inferred_type = "Source"
    
    current_type = data.get("type")
    if not current_type or current_type in ["wiki", "Article", "Concept", "RawSource", "Reference", "Source"]:
        data["type"] = inferred_type

    # 2. Field renames
    # abstract -> description
    if "abstract" in data and "description" not in data:
        data["description"] = data.pop("abstract")
    # updated -> timestamp (ISO 8601)
    if "updated" in data and "timestamp" not in data:
        updated_val = data.pop("updated")
        # try to parse old YYYY-MM-DD HH:mm or similar
        try:
            dt = datetime.strptime(updated_val.strip(), "%Y-%m-%d %H:%M")
            data["timestamp"] = dt.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        except Exception:
            try:
                dt = datetime.strptime(updated_val.strip(), "%Y-%m-%d")
                data["timestamp"] = dt.strftime("%Y-%m-%dT00:00:00+09:00")
            except Exception:
                data["timestamp"] = updated_val
    
    # created -> ISO 8601
    if "created" in data:
        created_val = data["created"]
        try:
            dt = datetime.strptime(created_val.strip(), "%Y-%m-%d %H:%M")
            data["created"] = dt.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        except Exception:
            try:
                dt = datetime.strptime(created_val.strip(), "%Y-%m-%d")
                data["created"] = dt.strftime("%Y-%m-%dT00:00:00+09:00")
            except Exception:
                pass

    # 3. Ensure title
    if "title" not in data or not data["title"]:
        # Try to find H1 in body
        h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if h1_match:
            data["title"] = h1_match.group(1).strip()
        else:
            data["title"] = file_path.stem

    # 4. Migrate '## 🔗 関連リンク' -> '# Citations'
    # Use case-insensitive find for sections like ## 🔗 関連リンク or ## 関連リンク
    citation_section_pattern = re.compile(
        r"##\s*(?:🔗\s*)?(?:関連リンク|Citations|引用文献)\n(.*?)(?=\n##|\n#|$)", 
        re.DOTALL | re.IGNORECASE
    )
    
    match = citation_section_pattern.search(body)
    if match:
        links_content = match.group(1).strip()
        # Remove the old section
        body = citation_section_pattern.sub("", body).strip()
        # Add OKF # Citations section at the end of the body
        # Clean double blank lines
        body = body.rstrip()
        body += f"\n\n# Citations\n{links_content}"

    # Validate with Schema
    try:
        validated = WikiFrontmatterSchema.model_validate(data)
        final_data = validated.model_dump(exclude_none=True)
    except Exception as ve:
        print(f"⚠️ Validation warning for {file_path.name}: {ve}")
        final_data = data

    new_fm_str = dump_frontmatter(final_data)
    new_content = f"{new_fm_str}\n{body}\n"

    if content != new_content:
        if dry_run:
            print(f"[DRY-RUN] Will update: {file_path}")
        else:
            file_path.write_text(new_content, encoding="utf-8")
            print(f"✅ Migrated: {file_path}")

def migrate_log_file(log_path: Path, dry_run: bool):
    if not log_path.exists():
        return
    
    print(f"Analyzing log file: {log_path}")
    content = log_path.read_text(encoding="utf-8")
    
    # Parse old format: ## [YYYY-MM-DD HH:mm] action | details
    # Or ## YYYY-MM-DD
    lines = content.splitlines()
    entries_by_date = {}
    
    current_date = None
    
    log_pattern = re.compile(r"^##\s+\[(\d{4}-\d{2}-\d{2})\s+[^\]]+\]\s+(\w+)\s*\|\s*(.*)")
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if matches old log pattern
        match = log_pattern.match(line)
        if match:
            date_str = match.group(1)
            action = match.group(2).capitalize()
            details = match.group(3)
            # convert wiki links to OKF standard relative links if possible
            # e.g. [[Self-RAG]] -> [Self-RAG](/concepts/self-rag.md) or similar
            # For logs, standard markdown links to bundle are best, but we keep text mostly intact
            details_clean = re.sub(r"\[\[([^|#\]]+)(?:[|#][^\]]+)?\]\]", r"[\1](\1.md)", details)
            
            entry = f"* **{action}**: {details_clean}."
            entries_by_date.setdefault(date_str, []).append(entry)
        elif line.startswith("## "):
            # Already a date heading
            date_val = line.replace("##", "").strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
                current_date = date_val
        elif line.startswith("* ") and current_date:
            entries_by_date.setdefault(current_date, []).append(line)
            
    # Rebuild log content in OKF format
    new_log = ["# Directory Update Log\n"]
    for date_str in sorted(entries_by_date.keys(), reverse=True):
        new_log.append(f"## {date_str}")
        for entry in entries_by_date[date_str]:
            new_log.append(entry)
        new_log.append("")
        
    new_content = "\n".join(new_log).strip() + "\n"
    if dry_run:
        print("[DRY-RUN] Will update log file to OKF format")
    else:
        log_path.write_text(new_content, encoding="utf-8")
        print("✅ Converted log.md to OKF format")

def main():
    args = setup_argparse()
    wiki_dir = Path(args.wiki_dir).resolve()
    
    if not wiki_dir.exists():
        print(f"❌ Wiki directory does not exist: {wiki_dir}")
        sys.exit(1)
        
    if args.backup and not args.dry_run:
        backup_wiki(wiki_dir)
        
    # 1. Rename Home.md -> index.md if it exists
    home_md = wiki_dir / "Home.md"
    if home_md.exists():
        if args.dry_run:
            print("[DRY-RUN] Will rename Home.md to index.md")
        else:
            index_md = wiki_dir / "index.md"
            if index_md.exists():
                os.remove(index_md)
            home_md.rename(index_md)
            print("✅ Renamed Home.md to index.md")

    # 2. Iterate through all .md files (except index.md and log.md)
    reserved_files = {"index.md", "log.md"}
    for md_file in wiki_dir.rglob("*.md"):
        if md_file.name in reserved_files:
            continue
        migrate_frontmatter_and_content(md_file, wiki_dir, args.dry_run)
        
    # 3. Convert log.md if it exists
    migrate_log_file(wiki_dir / "log.md", args.dry_run)
    
    # 4. Generate/Update index.md files
    if not args.dry_run:
        # Use ObsidianWriter's update_index logic to build all index files
        from output.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter(wiki_dir=str(wiki_dir))
        writer.update_index()
        print("✅ Regenerated all index.md files in OKF format")
        
    print("🎉 Migration completed!")

if __name__ == "__main__":
    main()
