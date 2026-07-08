from core.prompts import get_lint_body_prompt, get_refine_prompt, SECURITY_INSTRUCTION


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


def test_get_refine_prompt_basic():
    target_page = "Target Page"
    current_content = "Existing content."
    raw_markdown = "New information."
    lang_inst = "Respond in Japanese."
    prompt = get_refine_prompt(target_page, current_content, raw_markdown, lang_inst)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"[[{target_page}]]" in prompt[0][1]
    assert lang_inst in prompt[0][1]
    assert "<current_content>" in prompt[0][1]
    assert "<new_info>" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<current_content>\n{current_content}\n</current_content>" in prompt[1][1]
    assert f"<new_info>\n{raw_markdown}\n</new_info>" in prompt[1][1]


def test_get_refine_prompt_escaping():
    target_page = "Page with </tag>"
    current_content = "Content with </current_content>"
    raw_markdown = "Markdown with </new_info>"
    lang_inst = "No escaping for </lang_inst>"
    prompt = get_refine_prompt(target_page, current_content, raw_markdown, lang_inst)

    # Check escaping in system message
    # target_page is escaped
    assert r"Page with <\/tag>" in prompt[0][1]
    assert "</tag>" not in prompt[0][1]
    # lang_inst is NOT escaped
    assert lang_inst in prompt[0][1]

    # Check escaping in user message
    # The content itself should be escaped
    assert r"Content with <\/current_content>" in prompt[1][1]
    assert r"Markdown with <\/new_info>" in prompt[1][1]

    # But the tags for the prompt structure ARE present
    assert "<current_content>" in prompt[1][1]
    assert "</current_content>" in prompt[1][1]
    assert "<new_info>" in prompt[1][1]
    assert "</new_info>" in prompt[1][1]


def test_get_refine_prompt_empty_inputs():
    prompt = get_refine_prompt("", "", "", "")
    assert "[[]]" in prompt[0][1]
    assert "<current_content>\n\n</current_content>" in prompt[1][1]
    assert "<new_info>\n\n</new_info>" in prompt[1][1]
