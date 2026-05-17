import pytest
from core.utils import extract_json_from_text

def test_extract_json_markdown():
    text = "Here is some json:\n```json\n{\"key\": \"value\"}\n```\nHope it helps."
    expected = "{\"key\": \"value\"}"
    assert extract_json_from_text(text) == expected

def test_extract_json_raw():
    text = "Just raw json: {\"foo\": 123}"
    expected = "{\"foo\": 123}"
    assert extract_json_from_text(text) == expected

def test_extract_json_markdown_with_extra_spaces():
    text = "```json   \n{\"a\": 1}   \n```"
    expected = "{\"a\": 1}"
    assert extract_json_from_text(text) == expected

def test_extract_json_no_json():
    text = "No json here."
    assert extract_json_from_text(text) is None

def test_extract_json_nested_braces():
    text = "Some text before {\"outer\": {\"inner\": 1}} some text after"
    expected = "{\"outer\": {\"inner\": 1}}"
    assert extract_json_from_text(text) == expected

def test_extract_json_malformed_braces():
    # Only opening brace
    assert extract_json_from_text("This { has no end") is None
    # Only closing brace
    assert extract_json_from_text("This } has no start") is None

def test_extract_json_inverted_braces():
    # Closing brace before opening brace
    assert extract_json_from_text("Closing } before opening {") is None

def test_extract_json_multiple_blocks():
    # Currently it takes the first match for ```json
    text = "```json\n{\"first\": 1}\n```\n```json\n{\"second\": 2}\n```"
    assert extract_json_from_text(text) == "{\"first\": 1}"

def test_extract_json_fallback_with_extra_text():
    # Test fallback when ```json is missing but braces are present
    text = "Intro { \"key\": \"value\" } Outro"
    assert extract_json_from_text(text) == "{ \"key\": \"value\" }"

def test_extract_json_non_greedy():
    # Should find the first balanced object, not everything until the last brace
    text = "First { \"a\": 1 } and Second { \"b\": 2 }"
    result = extract_json_from_text(text)
    assert result == "{ \"a\": 1 }"

def test_extract_json_complex_nesting():
    text = "Text { \"a\": { \"b\": [1, 2], \"c\": { \"d\": 3 } } } extra"
    expected = "{ \"a\": { \"b\": [1, 2], \"c\": { \"d\": 3 } } }"
    assert extract_json_from_text(text) == expected
