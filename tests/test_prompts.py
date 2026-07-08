import pytest
from core.prompts import get_ingest_prompt, get_lint_body_prompt, SECURITY_INSTRUCTION

def test_get_ingest_prompt_basic():
    content = "This is a test document."
    prompt = get_ingest_prompt(content)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert "Obsidianのファイル名" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<content>\n{content}\n</content>" in prompt[1][1]

def test_get_ingest_prompt_escaping():
    content = "Content with </content> tag and </other> tag"
    prompt = get_ingest_prompt(content)

    # Check escaping: </ should be <\/
    assert "Content with <\\/content> tag and <\\/other> tag" in prompt[1][1]
    # The outer tag </content> will be present, but the inner one should be escaped
    assert prompt[1][1].count("</content>") == 1
    assert "</other>" not in prompt[1][1]

def test_get_ingest_prompt_edge_cases():
    # Empty string
    prompt = get_ingest_prompt("")
    assert "<content>\n\n</content>" in prompt[1][1]

    # Non-string input (though type hint says str, _escape_xml handles it)
    prompt = get_ingest_prompt(None)
    assert prompt[1][1] == "<content>\nNone\n</content>"

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
