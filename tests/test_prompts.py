import pytest
from core.prompts import (
    get_lint_body_prompt,
    get_metadata_prompt,
    get_ingest_prompt,
    get_fallback_prompt,
    get_translation_prompt,
    get_judgment_prompt,
    get_refine_prompt,
    get_draft_body_prompt,
    get_query_prompt,
    get_synthesis_prompt,
    SECURITY_INSTRUCTION,
)

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
    body = "Wiki body content"
    title_or_term = "RAG"
    prompt = get_metadata_prompt(body, title_or_term)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"title: 記事のタイトル（{title_or_term}）" in prompt[0][1]
    assert "description" in prompt[0][1]
    assert "concepts" in prompt[0][1]
    assert "tags" in prompt[0][1]
    assert f"aliases: タイトル '{title_or_term}'" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<body>\n{body}\n</body>" in prompt[1][1]

def test_get_metadata_prompt_escaping():
    body = "Body with </body"
    title_or_term = "Title with </title"
    prompt = get_metadata_prompt(body, title_or_term)

    assert "Body with <\\/body" in prompt[1][1]
    assert "Title with <\\/title" in prompt[0][1]

    # Check that the escaped versions are present and the raw input (as a sequence) is not.
    # Note: we can't just check for "</body" not in prompt[1][1] because of the </body> tag.
    # We check that the escaped sequence from the input exists.
    assert "</body\n" not in prompt[1][1]
    assert "</title\n" not in prompt[0][1]

def test_get_metadata_prompt_empty_inputs():
    prompt = get_metadata_prompt("", "")
    assert "title: 記事のタイトル（）" in prompt[0][1]
    assert "<body>\n\n</body>" in prompt[1][1]

def test_get_ingest_prompt():
    content = "Some content"
    prompt = get_ingest_prompt(content)
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"<content>\n{content}\n</content>" in prompt[1][1]

def test_get_fallback_prompt():
    body = "Some body"
    prompt = get_fallback_prompt(body)
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"<text>\n{body}\n</text>" in prompt[1][1]

def test_get_translation_prompt():
    term = "Term"
    prompt = get_translation_prompt(term)
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"<term>{term}</term>" in prompt[1][1]

def test_get_judgment_prompt():
    target = "Target"
    raw = "Raw"
    prompt = get_judgment_prompt(target, raw)
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"ターゲット: {target}" in prompt[0][1]
    assert f"<new_info>\n{raw}\n</new_info>" in prompt[1][1]

def test_get_refine_prompt():
    target = "Target"
    current = "Current"
    raw = "Raw"
    lang = "Use Japanese."
    prompt = get_refine_prompt(target, current, raw, lang)
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"[[{target}]]" in prompt[0][1]
    assert lang in prompt[0][1]
    assert f"<current_content>\n{current}\n</current_content>" in prompt[1][1]
    assert f"<new_info>\n{raw}\n</new_info>" in prompt[1][1]

def test_get_draft_body_prompt():
    target = "Target"
    raw = "Raw"
    context = "Context"
    prompt = get_draft_body_prompt(target, raw, context)
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"# {target}" in prompt[0][1]
    assert f"<new_info>\n{raw}\n</new_info>" in prompt[1][1]
    assert f"<context>\n{context}\n</context>" in prompt[1][1]

def test_get_query_prompt():
    query = "Query"
    context = "Context"
    lang = "Use Japanese."
    prompt = get_query_prompt(query, context, lang)
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert lang in prompt[0][1]
    assert f"<context>\n{context}\n</context>" in prompt[1][1]
    assert f"<query>\n{query}\n</query>" in prompt[1][1]

def test_get_synthesis_prompt():
    topic = "Topic"
    context = "Context"
    prompt = get_synthesis_prompt(topic, context)
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert f"トピック: {topic}" in prompt[0][1]
    assert f"<context>\n{context}\n</context>" in prompt[1][1]
