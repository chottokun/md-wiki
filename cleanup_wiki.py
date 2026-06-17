import os
import sys
import argparse
import re
import yaml

def parse_args():
    parser = argparse.ArgumentParser(description="Wiki dataset cleanup utility.")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying files.")
    parser.add_argument("--yes", action="store_true", help="Automatically apply changes.")
    parser.add_argument("--dir", default="wiki", help="Target wiki directory path.")
    return parser.parse_args()

def clean_file_content(content, title, filename):
    """
    Cleans up legacy AI update suggestions / diff blocks from the markdown body.
    Returns (cleaned_content, changed)
    """
    parts = content.split("---", 2)
    if len(parts) < 3:
        return content, False
    
    frontmatter = parts[1]
    body = parts[2]
    
    # Check if the body contains update suggestions or diff markers
    if not ("> [!info] AIからの更新提案" in body or "```diff" in body):
        return content, False
    
    # Identify the title to search for (clean title based on frontmatter or filename)
    search_title = (title or filename).lower().strip().replace("_", " ").replace("-", " ")
    
    lines = body.splitlines()
    clean_start_idx = -1
    
    for i, line in enumerate(lines):
        # We look for a line that starts exactly with H1 header "# " and matches the title
        if line.startswith("# "):
            line_title = line[2:].lower().strip().replace("_", " ").replace("-", " ")
            if line_title == search_title or search_title in line_title or line_title in search_title:
                clean_start_idx = i
                # Stop at the last occurrence of such line if multiple exist, or first clean one
                # In our files, the clean content starts after the diff block
    
    if clean_start_idx != -1:
        clean_body = "\n".join(lines[clean_start_idx:])
        # Rebuild file
        cleaned_content = f"---{frontmatter}---\n\n{clean_body}\n"
        return cleaned_content, True
    
    # Fallback: if we found diff but didn't match the title H1 exactly, look for any line starting exactly with H1
    for i, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("# Citations"):
            # Ensure it doesn't look like it's inside a diff block (no leading spaces or symbols)
            # Lines in diff block either start with > or space or +/-
            clean_start_idx = i
            break
            
    if clean_start_idx != -1:
        clean_body = "\n".join(lines[clean_start_idx:])
        cleaned_content = f"---{frontmatter}---\n\n{clean_body}\n"
        return cleaned_content, True

    return content, False

def load_frontmatter(content):
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}

def main():
    args = parse_args()
    wiki_dir = args.dir
    
    if not os.path.exists(wiki_dir):
        print(f"Error: Directory '{wiki_dir}' does not exist.")
        sys.exit(1)
        
    print(f"Scanning '{wiki_dir}' for quality issues...")
    
    files_to_clean = []
    empty_files = []
    
    # Recursively find all markdown files
    for root, dirs, files in os.walk(wiki_dir):
        for file in files:
            if file.endswith(".md") and file != "log.md" and file != "index.md":
                filepath = os.path.join(root, file)
                filename = os.path.splitext(file)[0]
                
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                meta = load_frontmatter(content)
                title = meta.get("title") or filename
                
                # Check for diff pollution
                cleaned, changed = clean_file_content(content, title, filename)
                if changed:
                    files_to_clean.append((filepath, content, cleaned))
                    
                # Check if body is empty or just whitespace
                parts = content.split("---", 2)
                body = parts[2].strip() if len(parts) >= 3 else content.strip()
                if not body or body == "":
                    empty_files.append(filepath)
                    
    print(f"\n--- Results ---")
    print(f"Found {len(files_to_clean)} files with diff pollution:")
    for path, _, _ in files_to_clean:
        print(f"  - {path}")
        
    print(f"\nFound {len(empty_files)} empty/stub files with no body content:")
    for path in empty_files:
        print(f"  - {path}")
        
    # Apply changes if permitted
    if not args.dry_run and (args.yes or input("\nApply cleanup changes? (y/N): ").lower() == 'y'):
        for path, _, cleaned in files_to_clean:
            with open(path, "w", encoding="utf-8") as f:
                f.write(cleaned)
            print(f"Cleaned: {path}")
        print("Cleanup completed.")
    else:
        print("\nDry-run mode or cleanup cancelled. No files modified.")

if __name__ == "__main__":
    main()
