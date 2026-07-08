import pytest
from core.utils import auto_link_concepts

def test_auto_link_basic():
    body = "This is about Machine Learning."
    concepts = ["Machine Learning"]
    expected = "This is about [[Machine Learning]]."
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_multiple_priority():
    # Longer concepts should be linked first
    body = "Deep Learning is a subset of Machine Learning."
    concepts = ["Deep Learning", "Machine Learning"]
    expected = "[[Deep Learning]] is a subset of [[Machine Learning]]."
    assert auto_link_concepts(body, concepts) == expected

    # Test overlapping but different concepts
    body = "We use Deep Learning."
    concepts = ["Learning", "Deep Learning"]
    # "Deep Learning" should be linked, and "Learning" should not be linked inside it.
    expected = "We use [[Deep Learning]]."
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_avoid_code_blocks():
    # Current implementation handles triple backticks
    body = "Outside\n```python\nMachine Learning\n```\nOutside again Machine Learning."
    concepts = ["Machine Learning"]
    expected = "Outside\n```python\nMachine Learning\n```\nOutside again [[Machine Learning]]."
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_avoid_headers():
    body = "# Machine Learning\nMachine Learning is cool."
    concepts = ["Machine Learning"]
    # Header should be avoided
    expected = "# Machine Learning\n[[Machine Learning]] is cool."
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_avoid_existing_links():
    body = "Already [[Machine Learning]] and new Machine Learning."
    concepts = ["Machine Learning"]
    # The first one should stay same (not double linked), second one should be linked.
    # Actually, the placeholder logic for existing links:
    # body = re.sub(r"\[\[.*?\]\]", link_repl, body)
    # protects the existing link.
    expected = "Already [[Machine Learning]] and new [[Machine Learning]]."
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_dash_normalization():
    # DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D"
    body = "Retrieval\u2010Augmented Generation"
    concepts = ["Retrieval-Augmented Generation"]
    expected = "[[Retrieval-Augmented Generation]]"
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_word_boundaries():
    body = "DeepLearning is not the same as Deep Learning."
    concepts = ["Learning"]
    # "Learning" in "DeepLearning" should not be matched because of (?<![A-Za-z0-9_\-])
    expected = "DeepLearning is not the same as Deep [[Learning]]."
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_stopwords():
    body = "用語名, title, abstract, concept should not be linked."
    concepts = ["用語名", "title", "abstract", "concept", "linkable"]
    body_with_linkable = body + " linkable"
    expected = body + " [[linkable]]"
    assert auto_link_concepts(body_with_linkable, concepts) == expected

def test_auto_link_short_terms():
    body = "A is not linked, but AB is."
    concepts = ["A", "AB"]
    expected = "A is not linked, but [[AB]] is."
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_empty_inputs():
    assert auto_link_concepts("", ["Concept"]) == ""
    assert auto_link_concepts("Body", []) == "Body"
    assert auto_link_concepts(None, ["Concept"]) is None

def test_auto_link_incremental_protection():
    # Test that once a term is linked, it's protected from shorter terms
    body = "Machine Learning"
    concepts = ["Machine Learning", "Learning"]
    # "Machine Learning" linked first. "Learning" should not match inside "[[Machine Learning]]"
    expected = "[[Machine Learning]]"
    assert auto_link_concepts(body, concepts) == expected

def test_auto_link_multiline_header_avoidance():
    body = "Text\n\n# Header Machine Learning\n\nMore text Machine Learning."
    concepts = ["Machine Learning"]
    expected = "Text\n\n# Header Machine Learning\n\nMore text [[Machine Learning]]."
    assert auto_link_concepts(body, concepts) == expected
