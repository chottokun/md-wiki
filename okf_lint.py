import sys
import re
from pathlib import Path
from core.utils import parse_frontmatter

def lint_wiki(wiki_dir_path: str) -> bool:
    wiki_dir = Path(wiki_dir_path).resolve()
    if not wiki_dir.exists():
        print(f"❌ Wiki directory does not exist: {wiki_dir}")
        return False

    reserved_files = {"index.md", "log.md"}
    all_md_files = list(wiki_dir.rglob("*.md"))
    
    concept_docs = [f for f in all_md_files if f.name not in reserved_files]
    
    valid_fm_count = 0
    non_empty_type_count = 0
    missing_desc_count = 0
    missing_timestamp_count = 0
    errors = []
    warnings = []

    # 1. Lint Concept/Article/Source Documents
    for f in concept_docs:
        try:
            content = f.read_text(encoding="utf-8")
            data, _ = parse_frontmatter(content)
            if data is None:
                errors.append(f"❌ {f.relative_to(wiki_dir)}: Missing or invalid YAML frontmatter")
                continue
            
            valid_fm_count += 1
            
            # Check required 'type' field
            doc_type = data.get("type")
            if not doc_type:
                errors.append(f"❌ {f.relative_to(wiki_dir)}: Required 'type' field is missing or empty")
            else:
                non_empty_type_count += 1

            # Check recommended fields
            if "description" not in data or not data["description"]:
                missing_desc_count += 1
                warnings.append(f"⚠️  {f.relative_to(wiki_dir)}: Missing recommended 'description' field")
            if "timestamp" not in data or not data["timestamp"]:
                missing_timestamp_count += 1
                warnings.append(f"⚠️  {f.relative_to(wiki_dir)}: Missing recommended 'timestamp' field")
        except Exception as e:
            errors.append(f"❌ {f.relative_to(wiki_dir)}: Failed to read/parse: {e}")

    # 2. Lint index.md files (§6 Conformance)
    index_files = list(wiki_dir.rglob("index.md"))
    valid_indexes = 0
    for idx_file in index_files:
        try:
            content = idx_file.read_text(encoding="utf-8")
            # index.md should NOT contain frontmatter
            if content.startswith("---"):
                errors.append(f"❌ {idx_file.relative_to(wiki_dir)}: index.md should NOT contain YAML frontmatter (§6)")
            else:
                valid_indexes += 1
        except Exception as e:
            errors.append(f"❌ {idx_file.relative_to(wiki_dir)}: Failed to read: {e}")

    # 3. Lint log.md (§7 Conformance)
    log_file = wiki_dir / "log.md"
    log_ok = True
    if log_file.exists():
        try:
            log_content = log_file.read_text(encoding="utf-8")
            if not log_content.startswith("# "):
                errors.append(f"❌ log.md: Must start with a top-level H1 header")
                log_ok = False
            
            # Simple check for OKF date format (## YYYY-MM-DD)
            date_headers = re.findall(r"^##\s+(\d{4}-\d{2}-\d{2})$", log_content, re.MULTILINE)
            if not date_headers:
                warnings.append("⚠️  log.md: No YYYY-MM-DD date headers found. Ensure OKF date group format is followed.")
        except Exception as e:
            errors.append(f"❌ log.md: Failed to read: {e}")
            log_ok = False
            
    # Print results
    print("\n=== OKF Conformance Report ===")
    print(f"Total concept documents found: {len(concept_docs)}")
    print(f"✅ {valid_fm_count}/{len(concept_docs)} documents have valid frontmatter")
    print(f"✅ {non_empty_type_count}/{len(concept_docs)} documents have non-empty 'type' field")
    print(f"✅ index.md files conformant: {valid_indexes}/{len(index_files)}")
    if log_file.exists():
        print(f"✅ log.md structure check: {'Passed' if log_ok else 'Failed'}")
    else:
        print("ℹ️  log.md not present in bundle")

    if warnings:
        print("\n--- Recommendations / Warnings ---")
        for w in warnings[:20]:  # Limit output
            print(w)
        if len(warnings) > 20:
            print(f"... and {len(warnings) - 20} more warnings.")

    if errors:
        print("\n--- Conformance Errors ---")
        for err in errors[:20]:
            print(err)
        if len(errors) > 20:
            print(f"... and {len(errors) - 20} more errors.")
        print("\nResult: NON-CONFORMANT")
        return False
    else:
        print("\nResult: CONFORMANT")
        return True

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "wiki"
    success = lint_wiki(target_dir)
    sys.exit(0 if success else 1)
