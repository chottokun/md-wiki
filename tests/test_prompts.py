import pytest
from core.prompts import get_lint_body_prompt, get_draft_body_prompt, SECURITY_INSTRUCTION

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

def test_get_draft_body_prompt_basic():
    target_page = "Test Page"
    raw_markdown = "Some raw content."
    context = "Existing context info."
    prompt = get_draft_body_prompt(target_page, raw_markdown, context)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    system_msg = prompt[0][1]
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in system_msg
    assert f"ターゲットタイトル: {target_page}" in system_msg
    assert f"# {target_page} (H1タイトル)" in system_msg
    assert "> [!abstract] 概要" in system_msg
    assert "<new_info>" in system_msg
    assert "<context>" in system_msg

    # User message
    user_msg = prompt[1][1]
    assert prompt[1][0] == "user"
    assert f"<new_info>\n{raw_markdown}\n</new_info>" in user_msg
    assert f"<context>\n{context}\n</context>" in user_msg

def test_get_draft_body_prompt_escaping():
    target_page = "Page </tag>"
    raw_markdown = "Markdown </info>"
    context = "Context </context>"
    prompt = get_draft_body_prompt(target_page, raw_markdown, context)

    # System message escaping
    assert "Page <\\/tag>" in prompt[0][1]
    assert "</tag>" not in prompt[0][1]

    # User message escaping
    assert "Markdown <\\/info>" in prompt[1][1]
    assert "Context <\\/context>" in prompt[1][1]
    assert "</info>" not in prompt[1][1]
    # Note: the actual tag <context> or <new_info> shouldn't be escaped if they are the wrapper tags,
    # but the content inside should be.
    # get_draft_body_prompt does:
    # f"<new_info>\n{raw_markdown}\n</new_info>\n\n<context>\n{context}\n</context>"
    # If raw_markdown contains </info>, it becomes <\\/info>
    assert "</info>" not in prompt[1][1]
    assert "</context>" in prompt[1][1] # This is the wrapper tag, but the inner one should be escaped
    assert "<\\/context>" in prompt[1][1]

def test_get_draft_body_prompt_empty():
    prompt = get_draft_body_prompt("", "", "")
    assert "ターゲットタイトル: " in prompt[0][1]
    assert "<new_info>\n\n</new_info>" in prompt[1][1]
