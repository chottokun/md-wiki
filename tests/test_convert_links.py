import pytest
from pathlib import Path
from convert_links import build_page_map, compute_relative_link, replace_wikilinks

def test_compute_relative_link():
    # Parent is "concepts", target is root
    assert compute_relative_link(Path("concepts/bleu-1.md"), Path("self_rag.md")) == "../self_rag.md"
    
    # Parent is root, target is "concepts/self_rag.md"
    assert compute_relative_link(Path("index.md"), Path("concepts/self_rag.md")) == "concepts/self_rag.md"
    
    # Parent is "concepts", target is "concepts/bm25.md"
    assert compute_relative_link(Path("concepts/bleu-1.md"), Path("concepts/bm25.md")) == "bm25.md"
    
    # Nested raw_markdown to concepts
    assert compute_relative_link(Path("raw_markdown/self_rag.md"), Path("concepts/self_rag.md")) == "../concepts/self_rag.md"

def test_replace_wikilinks():
    # Simple page map
    page_map = {
        "self_rag": Path("self_rag.md"),
        "dense passage retrieval": Path("concepts/dense_passage_retrieval.md"),
        "dpr": Path("concepts/dense_passage_retrieval.md"),
        "fever": Path("concepts/fever.md")
    }
    
    # 1. Simple link
    text = "This is a [[self_rag]] model."
    res, count = replace_wikilinks(text, Path("index.md"), page_map)
    assert count == 1
    assert res == "This is a [self_rag](self_rag.md) model."
    
    # 2. Link with alias
    text = "We use [[dense passage retrieval|DPR]] here."
    res, count = replace_wikilinks(text, Path("index.md"), page_map)
    assert count == 1
    assert res == "We use [DPR](concepts/dense_passage_retrieval.md) here."
    
    # 3. Link with anchor
    text = "Read [[self_rag#推論プロセス]] for details."
    res, count = replace_wikilinks(text, Path("concepts/fever.md"), page_map)
    assert count == 1
    assert res == "Read [self_rag](../self_rag.md#推論プロセス) for details."
    
    # 4. Same-file anchor link: [[#概要]]
    text = "See [[#概要]] below."
    res, count = replace_wikilinks(text, Path("concepts/fever.md"), page_map)
    assert count == 1
    assert res == "See [概要](#概要) below."
    
    # 5. Red link (not in page map) fallback
    text = "This links to a [[non_existent_page]]."
    # source is root
    res, count = replace_wikilinks(text, Path("index.md"), page_map)
    assert count == 1
    assert res == "This links to a [non_existent_page](concepts/non_existent_page.md)."
    
    # source is in concepts/
    res, count = replace_wikilinks(text, Path("concepts/fever.md"), page_map)
    assert count == 1
    assert res == "This links to a [non_existent_page](./non_existent_page.md)."
