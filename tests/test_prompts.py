import pytest
from core.prompts import get_lint_body_prompt, get_query_prompt, SECURITY_INSTRUCTION

def test_get_query_prompt_basic():
    query = "What is RAG?"
    context = "RAG stands for Retrieval-Augmented Generation."
    lang_inst = "Please answer in Japanese."
    prompt = get_query_prompt(query, context, lang_inst)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert lang_inst in prompt[0][1]
    assert "あなたはWikiのナレッジアシスタントです。" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<context>\n{context}\n</context>" in prompt[1][1]
    assert f"<query>\n{query}\n</query>" in prompt[1][1]

def test_get_query_prompt_escaping():
    query = "Query with </query> and </injection> tags"
    context = "Context with </context> and </injection> tags"
    lang_inst = "En"
    prompt = get_query_prompt(query, context, lang_inst)

    # Check escaping: </ should be <\/
    assert "Query with <\\/query> and <\\/injection> tags" in prompt[1][1]
    assert "Context with <\\/context> and <\\/injection> tags" in prompt[1][1]

    # We expect exactly one </query> and one </context> (from the prompt template itself)
    # but zero </injection>
    assert prompt[1][1].count("</query>") == 1
    assert prompt[1][1].count("</context>") == 1
    assert "</injection>" not in prompt[1][1]

def test_get_query_prompt_lang_inst():
    query = "test"
    context = "test"
    lang_inst = "SPECIFIC_LANGUAGE_INSTRUCTION"
    prompt = get_query_prompt(query, context, lang_inst)

    # lang_inst should appear in system message
    assert lang_inst in prompt[0][1]
    # It appears twice in the implementation
    assert prompt[0][1].count(lang_inst) >= 1

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
