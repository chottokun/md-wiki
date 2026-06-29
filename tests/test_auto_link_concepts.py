import pytest
from core.utils import auto_link_concepts

def test_basic_linking():
    body = "This is a test case for auto-linking."
    concepts = ["test case"]
    expected = "This is a [[test case]] for auto-linking."
    assert auto_link_concepts(body, concepts) == expected

def test_longest_match():
    body = "Machine Learning is a subset of AI."
    concepts = ["Machine", "Machine Learning"]
    # Should link the longest match first
    expected = "[[Machine Learning]] is a subset of AI."
    assert auto_link_concepts(body, concepts) == expected

def test_code_block_exclusion():
    body = """
Here is some code:
```python
print("Machine Learning")
```
And here is text: Machine Learning.
"""
    concepts = ["Machine Learning"]
    # Inside code block should NOT be linked, but outside should be.
    result = auto_link_concepts(body, concepts)
    assert 'print("Machine Learning")' in result
    assert '[[Machine Learning]]' in result
    assert result.count('[[Machine Learning]]') == 1

def test_header_exclusion():
    body = """
# Machine Learning
This article is about Machine Learning.
"""
    concepts = ["Machine Learning"]
    # Header should NOT be linked
    result = auto_link_concepts(body, concepts)
    assert "# Machine Learning" in result
    assert "[[Machine Learning]]" in result
    assert result.count("[[Machine Learning]]") == 1

def test_existing_link_exclusion():
    body = "Already linked: [[Machine Learning]] and not linked: Machine Learning."
    concepts = ["Machine Learning"]
    # Existing links should be protected (no double brackets)
    result = auto_link_concepts(body, concepts)
    assert "[[Machine Learning]]" in result
    assert "[[[[Machine Learning]]]]" not in result
    assert result.count("[[Machine Learning]]") == 2

def test_word_boundaries():
    body = "DeepLearning is not the same as Learning."
    concepts = ["Learning"]
    # "Learning" inside "DeepLearning" should NOT be linked due to word boundaries.
    # But the standalone "Learning" SHOULD be linked.
    result = auto_link_concepts(body, concepts)
    assert "DeepLearning" in result
    assert "[[Learning]]" in result
    assert result.count("[[Learning]]") == 1
    assert "Deep[[Learning]]" not in result

def test_dash_normalization():
    # \u2013 is EN DASH
    body = "Check Self\u2013RAG performance."
    concepts = ["Self-RAG"]
    # Body dash should be normalized to standard hyphen, then matched
    expected = "Check [[Self-RAG]] performance."
    assert auto_link_concepts(body, concepts) == expected

def test_excluded_terms():
    body = "The title and abstract are Important."
    concepts = ["title", "abstract", "Important"]
    # "title" and "abstract" are hardcoded to be ignored in auto_link_concepts
    result = auto_link_concepts(body, concepts)
    assert "[[title]]" not in result
    assert "[[abstract]]" not in result
    assert "[[Important]]" in result

def test_short_terms():
    body = "A is a letter, AB is a word."
    concepts = ["A", "AB"]
    # Length < 2 should be ignored
    result = auto_link_concepts(body, concepts)
    assert "[[A]]" not in result
    assert "[[AB]]" in result

def test_overlapping_concepts():
    body = "Natural Language Processing is key."
    concepts = ["Natural Language", "Natural Language Processing"]
    # After "Natural Language Processing" is linked, it should be protected from "Natural Language"
    expected = "[[Natural Language Processing]] is key."
    assert auto_link_concepts(body, concepts) == expected

def test_multiple_occurrences():
    body = "RAG is good. RAG is fast."
    concepts = ["RAG"]
    expected = "[[RAG]] is good. [[RAG]] is fast."
    assert auto_link_concepts(body, concepts) == expected

def test_multiline_body():
    body = "First line: RAG\nSecond line: RAG"
    concepts = ["RAG"]
    expected = "First line: [[RAG]]\nSecond line: [[RAG]]"
    assert auto_link_concepts(body, concepts) == expected
