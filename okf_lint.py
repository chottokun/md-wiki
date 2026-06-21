import sys
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List
from core.utils import parse_frontmatter

@dataclass
class LintResult:
    valid_fm_count: int = 0
    non_empty_type_count: int = 0
    missing_desc_count: int = 0
    missing_timestamp_count: int = 0
    valid_indexes: int = 0
    log_ok: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

def _lint_concept_docs(wiki_dir: Path, concept_docs: List[Path], result: LintResult):
    """1. Lint Concept/Article/Source Documents"""
    for f in concept_docs:
        try:
            content = f.read_text(encoding="utf-8")
            data, _ = parse_frontmatter(content)
            if data is None:
                result.errors.append(f"❌ {f.relative_to(wiki_dir)}: Missing or invalid YAML frontmatter")
                continue
            
            result.valid_fm_count += 1
            
            # Check required 'type' field
            doc_type = data.get("type")
            if not doc_type:
                result.errors.append(f"❌ {f.relative_to(wiki_dir)}: Required 'type' field is missing or empty")
            else:
                result.non_empty_type_count += 1

            # Check recommended fields
            if "description" not in data or not data["description"]:
                result.missing_desc_count += 1
                result.warnings.append(f"⚠️  {f.relative_to(wiki_dir)}: Missing recommended 'description' field")
            if "timestamp" not in data or not data["timestamp"]:
                result.missing_timestamp_count += 1
                result.warnings.append(f"⚠️  {f.relative_to(wiki_dir)}: Missing recommended 'timestamp' field")
        except Exception as e:
            result.errors.append(f"❌ {f.relative_to(wiki_dir)}: Failed to read/parse: {e}")

def _lint_index_files(wiki_dir: Path, index_files: List[Path], result: LintResult):
    """2. Lint index.md files (§6 Conformance)"""
    for idx_file in index_files:
        try:
            content = idx_file.read_text(encoding="utf-8")
            # index.md should NOT contain frontmatter
            if content.startswith("---"):
                result.errors.append(f"❌ {idx_file.relative_to(wiki_dir)}: index.md should NOT contain YAML frontmatter (§6)")
            else:
                result.valid_indexes += 1
        except Exception as e:
            result.errors.append(f"❌ {idx_file.relative_to(wiki_dir)}: Failed to read: {e}")

def _lint_log_file(wiki_dir: Path, log_file: Path, result: LintResult):
    """3. Lint log.md (§7 Conformance)"""
    if log_file.exists():
        try:
            log_content = log_file.read_text(encoding="utf-8")
            if not log_content.startswith("# "):
                result.errors.append(f"❌ log.md: Must start with a top-level H1 header")
                result.log_ok = False
            
            # Simple check for OKF date format (## YYYY-MM-DD)
            date_headers = re.findall(r"^##\s+(\d{4}-\d{2}-\d{2})$", log_content, re.MULTILINE)
            if not date_headers:
                result.warnings.append("⚠️  log.md: No YYYY-MM-DD date headers found. Ensure OKF date group format is followed.")
        except Exception as e:
            result.errors.append(f"❌ log.md: Failed to read: {e}")
            result.log_ok = False

def _print_report(result: LintResult, concept_docs_count: int, index_files_count: int, log_file_exists: bool) -> bool:
    """Print results and return success status"""
    print("\n=== OKF Conformance Report ===")
    print(f"Total concept documents found: {concept_docs_count}")
    print(f"✅ {result.valid_fm_count}/{concept_docs_count} documents have valid frontmatter")
    print(f"✅ {result.non_empty_type_count}/{concept_docs_count} documents have non-empty 'type' field")
    print(f"✅ index.md files conformant: {result.valid_indexes}/{index_files_count}")

    if log_file_exists:
        print(f"✅ log.md structure check: {'Passed' if result.log_ok else 'Failed'}")
    else:
        print("ℹ️  log.md not present in bundle")

    if result.warnings:
        print("\n--- Recommendations / Warnings ---")
        for w in result.warnings[:20]:  # Limit output
            print(w)
        if len(result.warnings) > 20:
            print(f"... and {len(result.warnings) - 20} more warnings.")

    if result.errors:
        print("\n--- Conformance Errors ---")
        for err in result.errors[:20]:
            print(err)
        if len(result.errors) > 20:
            print(f"... and {len(result.errors) - 20} more errors.")
        print("\nResult: NON-CONFORMANT")
        return False
    else:
        print("\nResult: CONFORMANT")
        return True

def lint_wiki(wiki_dir_path: str) -> bool:
    wiki_dir = Path(wiki_dir_path).resolve()
    if not wiki_dir.exists():
        print(f"❌ Wiki directory does not exist: {wiki_dir}")
        return False

    reserved_files = {"index.md", "log.md"}
    all_md_files = list(wiki_dir.rglob("*.md"))

    concept_docs = [f for f in all_md_files if f.name not in reserved_files]
    index_files = list(wiki_dir.rglob("index.md"))
    log_file = wiki_dir / "log.md"

    result = LintResult()

    _lint_concept_docs(wiki_dir, concept_docs, result)
    _lint_index_files(wiki_dir, index_files, result)
    _lint_log_file(wiki_dir, log_file, result)

    return _print_report(result, len(concept_docs), len(index_files), log_file.exists())

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "wiki"
    success = lint_wiki(target_dir)
    sys.exit(0 if success else 1)
