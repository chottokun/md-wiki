import pytest
import pytest
from core.prompts import (
    get_judgment_prompt,
    get_lint_body_prompt,
    get_synthesis_prompt,
    get_refine_prompt,
    get_metadata_prompt,
    get_fallback_prompt,
    get_translation_prompt,
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


def test_get_fallback_prompt_basic():
    body = "This is a technical text about RAG and LLM."
    prompt = get_fallback_prompt(body)

    assert isinstance(prompt, list)
    assert len(prompt) == 2

    # System message
    assert prompt[0][0] == "system"
    assert SECURITY_INSTRUCTION in prompt[0][1]
    assert "専門的な技術用語" in prompt[0][1]
    assert "<text>" in prompt[0][1]

    # User message
    assert prompt[1][0] == "user"
    assert f"<text>\n{body}\n</text>" in prompt[1][1]


def test_get_fallback_prompt_escaping():
    body = "Text with </text> tag"
    prompt = get_fallback_prompt(body)

    # Check escaping: </ should be <\/
    assert "Text with <\\/text> tag" in prompt[1][1]
    assert prompt[1][1].count("</text>") == 1  # Only the outer closing tag


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
    assert "Term with <\\/term> tag" in prompt[1][1]
    assert prompt[1][1] == f"<term>Term with <\\/term> tag</term>"
