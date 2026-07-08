from core.utils import parse_and_filter_concepts

def test_basic_parsing():
    raw = "- NLP\n- RAG\n- System Engineering"
    result = parse_and_filter_concepts(raw)
    assert result == ["NLP", "RAG", "System Engineering"]

def test_remove_citations_and_parentheses():
    """引用 (et al) や片方だけの括弧を持つゴミが除去されること。"""
    raw = "- Valid Concept\n- Retrieval (Lewis et al., 2020)\n- 2020)\n- et al. model"
    result = parse_and_filter_concepts(raw)
    assert "Valid Concept" in result
    assert "Retrieval (Lewis et al., 2020)" not in result
    assert "2020)" not in result
    assert "et al. model" not in result

def test_remove_punctuation_and_links():
    """末尾の句読点や、LLMが誤って付与した [[ ]] が除去されること。"""
    raw = "- ConceptA.\n- [[ConceptB]],\n- ConceptC;"
    result = parse_and_filter_concepts(raw)
    assert "ConceptA" in result
    assert "ConceptB" in result
    assert "ConceptC" in result

def test_remove_duplicates_and_ignore_non_list():
    """重複が排除され、箇条書き(-)以外の行が無視されること。"""
    raw = "Here are the concepts:\n- LLM\n- RAG\n- LLM\nThese are important."
    result = parse_and_filter_concepts(raw)
    assert result == ["LLM", "RAG"]

def test_filter_short_terms():
    raw = "- A\n- AB\n- "
    result = parse_and_filter_concepts(raw)
    assert "AB" in result
    assert "A" not in result
    assert "" not in result

def test_filter_blacklisted_terms():
    raw = "- 用語名\n- title\n- Abstract\n- CONCEPT\n- Valid"
    result = parse_and_filter_concepts(raw)
    assert result == ["Valid"]

def test_unbalanced_parentheses():
    raw = "- Normal (nested)\n- Unbalanced)\n- (Another unbalanced"
    result = parse_and_filter_concepts(raw)
    assert "Normal (nested)" in result
    assert "Unbalanced)" not in result
    # 現状のコードは `")" in c and "(" not in c` のみチェックしているため、
    # 開始括弧のみの場合は除去されない。
    assert "(Another unbalanced" in result

def test_mixed_noises():
    raw = """
    - [[Deep Learning]]
    - et al. (2023)
    - term with comma,
    - x
    - [[title]]
    - Proper Term
    """
    result = parse_and_filter_concepts(raw)
    assert result == ["Deep Learning", "term with comma", "Proper Term"]

def test_empty_input():
    assert parse_and_filter_concepts("") == []
    assert parse_and_filter_concepts("\n\n") == []

def test_no_bullet_points():
    raw = "Just some text\nwithout bullets"
    assert parse_and_filter_concepts(raw) == []
