import pytest
from core.prompts import get_lint_body_prompt, get_translation_prompt, SECURITY_INSTRUCTION

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

def test_get_translation_prompt_basic():
    term = "ベクトル検索"
    prompt = get_translation_prompt(term)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert "Translate the technical term" in prompt[0][1]
    assert "Output ONLY the translated term" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<term>{term}</term>" in prompt[1][1]

def test_get_translation_prompt_escaping():
    term = "Term with </term> tag"
    prompt = get_translation_prompt(term)

    # Check escaping: </ should be <\/
    # The term itself should be escaped
    assert "Term with <\\/term> tag" in prompt[1][1]
    # The whole user message should have the escaped content inside legitimate tags
    assert prompt[1][1] == f"<term>Term with <\\/term> tag</term>"
