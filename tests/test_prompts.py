import pytest
from core.prompts import get_lint_body_prompt, get_synthesis_prompt, SECURITY_INSTRUCTION

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

def test_get_synthesis_prompt_escaping():
    topic = "Topic with </system> tag"
    context = "Context with </source> tag"
    prompt = get_synthesis_prompt(topic, context)

    # Check escaping: </ should be <\/
    assert "Topic with <\\/system> tag" in prompt[0][1]
    assert "Context with <\\/source> tag" in prompt[1][1]
    assert "</system>" not in prompt[0][1]
    assert "</source>" not in prompt[1][1]

def test_get_synthesis_prompt_empty():
    prompt = get_synthesis_prompt("", "")
    assert "トピック: " in prompt[0][1]
    assert "<context>\n\n</context>" in prompt[1][1]

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

def test_get_synthesis_prompt_basic():
    topic = "AI Agents"
    context = "Research on autonomous agents."
    prompt = get_synthesis_prompt(topic, context)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"トピック: {topic}" in prompt[0][1]
    assert "高度なナレッジマネージャー" in prompt[0][1]
    assert "<context>" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<context>\n{context}\n</context>" in prompt[1][1]
