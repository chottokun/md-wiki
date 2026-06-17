import os
import sys
import re
import argparse
import shutil
from pathlib import Path
import yaml
from core.utils import parse_frontmatter, normalize_term

def parse_args():
    parser = argparse.ArgumentParser(description="Convert Obsidian wikilinks to standard Markdown relative links.")
    parser.add_argument("--out-dir", default="dist/wiki", help="Output directory (default: dist/wiki)")
    parser.add_argument("--inplace", action="store_true", help="Modify source files directly inside the wiki folder")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--dir", default="wiki", help="Target source wiki directory (default: wiki)")
    return parser.parse_args()

def build_page_map(wiki_dir: Path) -> dict[str, Path]:
    """
    Scans the wiki folder to build a mapping from notes stems, titles,
    and aliases to their relative path within the vault.
    """
    page_map = {}
    for path in wiki_dir.rglob("*.md"):
        if path.name in ["index.md", "log.md"]:
            # Standard index/logs don't represent unique linkable concepts,
            # but we can resolve them if explicitly referenced.
            pass
            
        rel_path = path.relative_to(wiki_dir)
        
        # 1. Stem (filename without extension, e.g. "self_rag")
        stem = path.stem
        page_map[stem.lower()] = rel_path
        page_map[stem.replace("_", " ").lower()] = rel_path
        page_map[stem.replace("-", " ").lower()] = rel_path
        page_map[stem.replace("_", "-").lower()] = rel_path
        page_map[stem.replace("-", "_").lower()] = rel_path
        
        # 2. Parse frontmatter for title and aliases
        try:
            content = path.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(content)
            if meta:
                # Title
                title = meta.get("title")
                if title:
                    page_map[title.lower()] = rel_path
                    page_map[title.replace("_", " ").lower()] = rel_path
                    page_map[title.replace("-", " ").lower()] = rel_path
                # Aliases
                aliases = meta.get("aliases") or []
                for alias in aliases:
                    page_map[alias.lower()] = rel_path
                    page_map[alias.replace("_", " ").lower()] = rel_path
                    page_map[alias.replace("-", " ").lower()] = rel_path
        except Exception:
            pass
            
    return page_map

def compute_relative_link(source_rel_path: Path, target_rel_path: Path) -> str:
    """Computes a relative markdown link path from source to target."""
    source_parent = source_rel_path.parent
    rel_path = os.path.relpath(target_rel_path, source_parent)
    # Replace Windows backslashes with standard forward slashes
    return rel_path.replace("\\", "/")

def replace_wikilinks(content: str, source_rel_path: Path, page_map: dict[str, Path]) -> tuple[str, int]:
    """
    Replaces [[Link]] syntax in content with standard markdown relative links.
    Returns (replaced_content, count)
    """
    # Pattern to match [[PageName]] or [[PageName#Section]] or [[PageName|Alias]] or [[#Section]]
    pattern = re.compile(r"\[\[([^\]|#]+)?(?:#([^\]|]+))?(?:\|([^\]]+))?\]\]")
    count = [0] # Mutable container to track replacements
    
    def repl(match):
        target_page = match.group(1)
        anchor = match.group(2)
        alias = match.group(3)
        
        # Determine display text
        if alias:
            display_text = alias
        elif target_page:
            display_text = target_page
        elif anchor:
            display_text = anchor
        else:
            display_text = ""
            
        count[0] += 1
        
        # 1. Same-file anchor link: [[#Section]]
        if not target_page:
            if anchor:
                anchor_slug = anchor.lower().strip().replace(" ", "-").replace("　", "-")
                anchor_slug = re.sub(r"[^\w\-]", "", anchor_slug)
                return f"[{display_text}](#{anchor_slug})"
            return match.group(0) # Invalid double brackets
            
        # 2. Cross-file link
        target_key = target_page.lower().strip()
        target_key_clean = target_key.replace("_", " ").replace("-", " ")
        
        target_rel_path = page_map.get(target_key) or page_map.get(target_key_clean)
        
        if target_rel_path:
            link_path = compute_relative_link(source_rel_path, target_rel_path)
        else:
            # Fallback for red links: guess relative concepts folder location
            target_norm = normalize_term(target_page) + ".md"
            rel_parts = source_rel_path.parent.parts
            if "concepts" in rel_parts:
                link_path = f"./{target_norm}"
            elif len(rel_parts) == 0:
                link_path = f"concepts/{target_norm}"
            else:
                depth = len(rel_parts)
                prefix = "../" * depth
                link_path = f"{prefix}concepts/{target_norm}"
                
        # Append anchor if present
        if anchor:
            anchor_slug = anchor.lower().strip().replace(" ", "-").replace("　", "-")
            anchor_slug = re.sub(r"[^\w\-]", "", anchor_slug)
            link_path = f"{link_path}#{anchor_slug}"
            
        return f"[{display_text}]({link_path})"
        
    replaced_content = pattern.sub(repl, content)
    return replaced_content, count[0]

def main():
    args = parse_args()
    source_dir = Path(args.dir).resolve()
    
    if not source_dir.exists():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        sys.exit(1)
        
    # Build note/page mapping
    print(f"Indexing wiki folder '{source_dir}'...")
    page_map = build_page_map(source_dir)
    print(f"Indexed {len(page_map)} page names and aliases.")
    
    # Track files for processing
    md_files = []
    other_files = []
    
    for root, dirs, files in os.walk(source_dir):
        # Exclude hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            path = Path(root) / file
            if file.endswith(".md"):
                md_files.append(path)
            else:
                other_files.append(path)
                
    # Dry run or confirm
    if args.dry_run:
        print("\n--- Dry Run Preview ---")
        for path in md_files:
            rel_path = path.relative_to(source_dir)
            content = path.read_text(encoding="utf-8")
            _, count = replace_wikilinks(content, rel_path, page_map)
            if count > 0:
                print(f"Will modify: {rel_path} ({count} links)")
        print("\nDry run completed. No files modified.")
        return
        
    if not args.inplace:
        out_dir = Path(args.out_dir).resolve()
        print(f"Exporting converted wiki to: {out_dir}")
        if out_dir.exists() and not args.yes:
            ans = input(f"Output directory '{out_dir}' already exists. Overwrite? (y/N): ")
            if ans.lower() != 'y':
                print("Aborted.")
                return
    else:
        print(f"Modifying files INPLACE inside: {source_dir}")
        if not args.yes:
            ans = input("This will overwrite the source files directly. Are you sure? (y/N): ")
            if ans.lower() != 'y':
                print("Aborted.")
                return
                
    # Process files
    converted_count = 0
    total_links_converted = 0
    
    for path in md_files:
        rel_path = path.relative_to(source_dir)
        content = path.read_text(encoding="utf-8")
        converted_content, count = replace_wikilinks(content, rel_path, page_map)
        
        if args.inplace:
            dest_path = path
        else:
            dest_path = out_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(converted_content if count > 0 else content)
            
        if count > 0:
            converted_count += 1
            total_links_converted += count
            print(f"Converted links in: {rel_path} ({count} links)")
        else:
            if not args.inplace:
                # Still copy non-changed files to target folder
                shutil.copy2(path, dest_path)
                
    # Copy other static assets (images, pdfs)
    if not args.inplace:
        for path in other_files:
            rel_path = path.relative_to(source_dir)
            dest_path = out_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest_path)
            
    print(f"\n🎉 Conversion completed!")
    print(f"Processed {len(md_files)} Markdown files.")
    print(f"Converted {total_links_converted} links across {converted_count} files.")

if __name__ == "__main__":
    main()
