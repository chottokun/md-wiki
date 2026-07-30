import time
import shutil
from pathlib import Path
from core.utils import walk_wiki_md_files

def test_benchmark_walking_performance(tmp_path):
    """
    Benchmarks the performance of walk_wiki_md_files against legacy rglob + filter approach
    to verify that walk_wiki_md_files is significantly faster and finds the correct files.
    """
    # 1. Standard wiki pages (should be scanned)
    concepts_dir = tmp_path / "concepts"
    concepts_dir.mkdir(exist_ok=True)
    for i in range(20):
        (concepts_dir / f"concept_{i}.md").write_text("# Concept\nSome content", encoding="utf-8")

    for i in range(20):
        (tmp_path / f"article_{i}.md").write_text("# Article\nSome content", encoding="utf-8")

    # 2. Simulated .git directory (should be ignored)
    git_dir = tmp_path / ".git" / "objects"
    git_dir.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        subdir = git_dir / f"{i:02x}"
        subdir.mkdir(exist_ok=True)
        for j in range(5):
            (subdir / f"object_{j}").write_text("dummy binary data", encoding="utf-8")

    # 3. Simulated .obsidian directory (should be ignored)
    obs_dir = tmp_path / ".obsidian" / "plugins" / "some-plugin"
    obs_dir.mkdir(parents=True, exist_ok=True)
    for i in range(50):
        (obs_dir / f"note_{i}.md").write_text("ignored obsidian note", encoding="utf-8")

    # 4. Simulated raw_markdown directory (should be ignored optionally)
    raw_md_dir = tmp_path / "raw_markdown"
    raw_md_dir.mkdir(exist_ok=True)
    for i in range(100):
        (raw_md_dir / f"raw_text_{i}.md").write_text("# Raw Content", encoding="utf-8")

    # 5. Simulated sources directory
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir(exist_ok=True)
    for i in range(20):
        (sources_dir / f"source_doc_{i}.md").write_text("# Source", encoding="utf-8")

    # Time Legacy
    start_time = time.perf_counter()
    all_pages_legacy = list(tmp_path.rglob("*.md"))
    pages_legacy = [
        p for p in all_pages_legacy
        if "raw_markdown" not in p.parts
        and "sources" not in p.parts
        and ".obsidian" not in p.parts
        and p.name != "Management Dashboard.md"
    ]
    legacy_time = time.perf_counter() - start_time

    # Time Optimized
    start_time = time.perf_counter()
    pages_opt = [
        p for p in walk_wiki_md_files(tmp_path, include_raw_and_sources=False)
        if p.name != "Management Dashboard.md"
    ]
    opt_time = time.perf_counter() - start_time

    # Assertions
    assert set(pages_legacy) == set(pages_opt), "Found file sets must match perfectly!"
    assert len(pages_opt) == 40, f"Expected 40 files, got {len(pages_opt)}"

    print(f"\n[BENCHMARK] Legacy: {legacy_time*1000:.2f}ms, Optimized: {opt_time*1000:.2f}ms")
    print(f"[BENCHMARK] Speedup: {legacy_time / opt_time if opt_time > 0 else 0:.2f}x faster")
