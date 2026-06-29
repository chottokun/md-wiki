import pytest
from core.utils import parse_and_filter_concepts

def test_basic_bullets():
    raw_output = "- Machine Learning\n- Artificial Intelligence"
    expected = ["Machine Learning", "Artificial Intelligence"]
    assert parse_and_filter_concepts(raw_output) == expected

def test_punctuation_stripping():
    raw_output = "- Concept A.\n- Concept B;\n- Concept C:\n- Concept D,"
    expected = ["Concept A", "Concept B", "Concept C", "Concept D"]
    assert parse_and_filter_concepts(raw_output) == expected

def test_bracket_removal():
    raw_output = "- [[Machine Learning]]\n- [[AI]]"
    expected = ["Machine Learning", "AI"]
    assert parse_and_filter_concepts(raw_output) == expected

def test_length_filter():
    raw_output = "- A\n- AI\n- "
    expected = ["AI"]
    assert parse_and_filter_concepts(raw_output) == expected

def test_unbalanced_parens():
    raw_output = "- (Valid)\n- Invalid)\n- Also (Valid)"
    expected = ["(Valid)", "Also (Valid)"]
    assert parse_and_filter_concepts(raw_output) == expected

def test_et_al_filter():
    raw_output = "- Smith et al.\n- Jones et al 2023\n- Valid Concept"
    expected = ["Valid Concept"]
    assert parse_and_filter_concepts(raw_output) == expected

def test_keyword_filter():
    raw_output = "- 用語名\n- Title\n- Abstract\n- Concept\n- Valid Topic"
    expected = ["Valid Topic"]
    assert parse_and_filter_concepts(raw_output) == expected

def test_deduplication():
    raw_output = "- AI\n- Machine Learning\n- AI"
    expected = ["AI", "Machine Learning"]
    assert parse_and_filter_concepts(raw_output) == expected

def test_mixed_input():
    raw_output = """
    Some header
    - Valid Concept 1
    - A
    - [[Link]]
    - Unbalanced)
    - Citation et al.
    - Title
    - Valid Concept 1
    - Valid Concept 2
    """
    expected = ["Valid Concept 1", "Link", "Valid Concept 2"]
    assert parse_and_filter_concepts(raw_output) == expected
