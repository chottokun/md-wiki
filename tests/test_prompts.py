from core.prompts import get_judgment_prompt, get_lint_body_prompt, SECURITY_INSTRUCTION


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


def test_get_judgment_prompt_basic():
    target_page = "DeepLearning"
    raw_markdown = "New info about neural networks."
    prompt = get_judgment_prompt(target_page, raw_markdown)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"ターゲット: {target_page}" in prompt[0][1]
    assert "<new_info>" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<new_info>\n{raw_markdown}\n</new_info>" in prompt[1][1]


def test_get_judgment_prompt_escaping():
    target_page = "Page with </target>"
    raw_markdown = "Markdown with </some_tag> tag."
    prompt = get_judgment_prompt(target_page, raw_markdown)

    # Check escaping: </ should be <\\/
    assert "Page with <\\/target>" in prompt[0][1]
    assert "Markdown with <\\/some_tag> tag." in prompt[1][1]
    assert "</target>" not in prompt[0][1]
    assert "</some_tag>" not in prompt[1][1]


def test_get_judgment_prompt_empty_inputs():
    prompt = get_judgment_prompt("", "")
    assert "ターゲット: " in prompt[0][1]
    assert "<new_info>\n\n</new_info>" in prompt[1][1]
