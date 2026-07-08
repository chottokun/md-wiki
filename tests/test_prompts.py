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
    body = "This is a wiki article about RAG."
    title_or_term = "RAG"
    prompt = get_metadata_prompt(body, title_or_term)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"title: 記事のタイトル（{title_or_term}）" in prompt[0][1]
    assert "<body> タグ内にあります" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<body>\n{body}\n</body>" in prompt[1][1]


def test_get_metadata_prompt_escaping():
    body = "Body with </inject> tag"
    title_or_term = "Term with </system> tag"
    prompt = get_metadata_prompt(body, title_or_term)

    # Check escaping: </ should be <\/
    assert "Body with <\\/inject> tag" in prompt[1][1]
    assert "Term with <\\/system> tag" in prompt[0][1]
    assert "</inject>" not in prompt[1][1]
    assert "</system>" not in prompt[0][1]
