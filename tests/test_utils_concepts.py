import pytest
from pathlib import Path
from core.utils import get_all_concepts, _get_all_concepts_internal

def test_get_all_concepts_returns_copy(tmp_path):
    # Setup a mock wiki dir
    wiki_dir = tmp_path / "wiki"
    concept_dir = wiki_dir / "concepts"
    concept_dir.mkdir(parents=True)
    (concept_dir / "test1.md").write_text("content", encoding="utf-8")
    
    # First call
    concepts1 = get_all_concepts(wiki_dir=str(wiki_dir))
    assert "test1" in concepts1
    
    # Modify the returned list
    concepts1.append("corrupted")
    
    # Second call (should hit cache but return a new list)
    concepts2 = get_all_concepts(wiki_dir=str(wiki_dir))
    assert "test1" in concepts2
    assert "corrupted" not in concepts2
    assert concepts1 is not concepts2

def test_get_all_concepts_cached_value(tmp_path):
    # Setup
    wiki_dir = tmp_path / "wiki"
    concept_dir = wiki_dir / "concepts"
    concept_dir.mkdir(parents=True)
    (concept_dir / "test1.md").write_text("content", encoding="utf-8")
    
    # Clear cache for this test to ensure it runs correctly
    _get_all_concepts_internal.cache_clear()
    
    concepts1 = get_all_concepts(wiki_dir=str(wiki_dir))
    
    # Add a new file - cache should NOT be updated because wiki_dir is same
    (concept_dir / "test2.md").write_text("content", encoding="utf-8")
    concepts2 = get_all_concepts(wiki_dir=str(wiki_dir))
    
    assert concepts1 == concepts2
    assert "test2" not in concepts2
    
    # Clear cache and check again
    _get_all_concepts_internal.cache_clear()
    concepts3 = get_all_concepts(wiki_dir=str(wiki_dir))
    assert "test2" in concepts3
