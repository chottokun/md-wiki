import pytest
from core.prompts import get_lint_body_prompt, get_fallback_prompt, SECURITY_INSTRUCTION

def test_get_lint_body_prompt_basic():
    term = "RAG"
    context = "Retrieval-Augmented Generation is useful."
    prompt = get_lint_body_prompt(term, context)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"技術用語 '{term}'" in prompt[0][1]
    assert "Markdown形式" in prompt[0][1]
    assert "<context>" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<context>\n{context}\n</context>" in prompt[1][1]

def test_get_lint_body_prompt_escaping():
    term = "Term with </system> tag"
    context = "Context with </content> tag"
    prompt = get_lint_body_prompt(term, context)

    # Check escaping: </ should be <\/
    assert "Term with <\\/system> tag" in prompt[0][1]
    assert "Context with <\\/content> tag" in prompt[1][1]
    assert "</system>" not in prompt[0][1]
    assert "</content>" not in prompt[1][1]

def test_get_lint_body_prompt_empty_inputs():
    prompt = get_lint_body_prompt("", "")
    assert "技術用語 ''" in prompt[0][1]
    assert "<context>\n\n</context>" in prompt[1][1]

def test_get_fallback_prompt_basic():
    body = "This is a technical text about RAG and LLM."
    prompt = get_fallback_prompt(body)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert "専門的な技術用語" in prompt[0][1]
    assert "<text>" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<text>\n{body}\n</text>" in prompt[1][1]

def test_get_fallback_prompt_escaping():
    body = "Text with </text> tag"
    prompt = get_fallback_prompt(body)

    # Check escaping: </ should be <\/
    # The body itself should be escaped, but the outer tags <text>...</text> remain.
    assert "Text with <\\/text> tag" in prompt[1][1]
    # Verify that the literal "</text>" from the input body is NOT present in the output
    # (it should be escaped). Note that the prompt structure itself ends with "</text>".
    # We check that the escaped version is there and the injection attempt is neutralized.
    assert prompt[1][1].count("</text>") == 1  # Only the outer closing tag
