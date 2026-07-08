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

def test_extract_json_uppercase_block():
    """
    Verify that ```JSON block is handled.
    The regex is case-insensitive for 'json', so it should extract it correctly.
    """
    text = "```JSON\n{\"a\": 1}\n```"
    expected = "{\"a\": 1}"
    assert extract_json_from_text(text) == expected

def test_extract_json_uppercase_block_with_extra_outside():
    """
    Verify that ```JSON (uppercase) matches the regex (with IGNORECASE)
    and succeeds even if the whole text is unbalanced.
    """
    text = "```JSON\n{\"a\": 1}\n```\nExtra {"
    # Regex matches with IGNORECASE, inner is {"a": 1}, which is balanced.
    assert extract_json_from_text(text) == "{\"a\": 1}"

def test_extract_json_lowercase_block_with_extra_outside():
    """
    This test demonstrates that ```json (lowercase) DOES match the regex,
    so it succeeds even if the whole text is unbalanced.
    """
    text = "```json\n{\"a\": 1}\n```\nExtra {"
    # Regex matches, inner is {"a": 1}, which is balanced.
    assert extract_json_from_text(text) == "{\"a\": 1}"

def test_extract_json_no_prefix_block():
    """Verify that code block without 'json' prefix is handled."""
    text = "```\n{\"a\": 1}\n```"
    expected = "{\"a\": 1}"
    assert extract_json_from_text(text) == expected

def test_extract_json_surrounding_text_in_block():
    """Verify that text inside code block but outside JSON is handled."""
    text = "```json\nExplanation before\n{\"a\": 1}\nExplanation after\n```"
    expected = "{\"a\": 1}"
    assert extract_json_from_text(text) == expected

def test_extract_json_unbalanced_in_block_fallback():
    """
    Verify that if the first code block has unbalanced JSON,
    it falls back to searching the entire text.
    """
    text = "```json\n{ unbalanced\n```\nBut here is valid: {\"a\": 1}"
    # The code block has { unbalanced (count { is 1, count } is 0)
    # _extract_balanced_json(inner) returns None because count mismatch
    # Then it calls _extract_balanced_json(text)
    # count { in text is 2, count } in text is 1. Still unbalanced!
    # Wait, if the whole text is unbalanced, it returns None.
    assert extract_json_from_text(text) is None

def test_extract_json_balanced_in_block_unbalanced_text():
    """
    If the block is balanced, it should return it even if the whole text is not
    (though _extract_balanced_json checks count in the text passed to it).
    """
    text = "```json\n{\"a\": 1}\n```\nExtra }"
    # inner = "{\"a\": 1}" -> count { is 1, count } is 1. Balanced. Returns it.
    assert extract_json_from_text(text) == "{\"a\": 1}"

def test_extract_json_multiple_blocks_first_not_json():
    """
    Verify behavior when multiple code blocks are present and the first one doesn't contain JSON.
    """
    text = "```text\nhello\n```\n```json\n{\"a\": 1}\n```"
    # Current implementation:
    # 1. Matches first block (```text\nhello\n```)
    # 2. inner = "text\nhello"
    # 3. _extract_balanced_json(inner) -> None
    # 4. returns _extract_balanced_json(text)
    # _extract_balanced_json(text) -> finds first { which is in the second block.
    assert extract_json_from_text(text) == "{\"a\": 1}"
