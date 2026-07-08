import pytest
from core.prompts import get_lint_body_prompt, get_metadata_prompt, SECURITY_INSTRUCTION

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

def test_get_metadata_prompt_basic():
    body = "This is a body about RAG."
    title = "RAG Title"
    prompt = get_metadata_prompt(body, title)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"title: 記事のタイトル（{title}）" in prompt[0][1]
    assert "<body>" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<body>\n{body}\n</body>" in prompt[1][1]

def test_get_metadata_prompt_escaping():
    body = "Body with </body> tag"
    title = "Title with </title> tag"
    prompt = get_metadata_prompt(body, title)

    # Check escaping: </ should be <\/
    assert "Body with <\\/body> tag" in prompt[1][1]
    assert "Title with <\\/title> tag" in prompt[0][1]

    # prompt[1][1] (user message) contains exactly one </body> (from template)
    assert prompt[1][1].count("</body>") == 1
    # prompt[0][1] (system message) does not contain any </title> because it was escaped
    assert "</title>" not in prompt[0][1]

def test_get_metadata_prompt_empty_inputs():
    prompt = get_metadata_prompt("", "")
    assert "title: 記事のタイトル（）" in prompt[0][1]
    assert "<body>\n\n</body>" in prompt[1][1]
