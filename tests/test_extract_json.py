import sys
from unittest.mock import MagicMock

# Mock dependencies before importing agent.graph
mock_modules = [
    "langgraph",
    "langgraph.graph",
    "langgraph.checkpoint.memory",
    "ingestion.docling_parser",
    "retrieval.qdrant_store",
    "output.obsidian_writer",
    "core.llm_router",
    "core.schemas",
    "docling",
    "docling.datamodel.base_models",
    "docling.datamodel.pipeline_external_base",
    "docling.document_converter",
    "qdrant_client",
]

for mod_name in mock_modules:
    sys.modules[mod_name] = MagicMock()

# Now import the function
try:
    from agent.graph import extract_json_from_text
except ImportError:
    sys.modules["agent.state"] = MagicMock()
    sys.modules["core.utils"] = MagicMock()
    sys.modules["core.prompts"] = MagicMock()
    from agent.graph import extract_json_from_text

def test_extract_json_markdown():
    text = "Here is some json:\n```json\n{\"key\": \"value\"}\n```\nHope it helps."
    expected = "{\"key\": \"value\"}"
    assert extract_json_from_text(text) == expected

def test_extract_json_raw():
    text = "Just raw json: {\"foo\": 123}"
    expected = "{\"foo\": 123}"
    assert extract_json_from_text(text) == expected

def test_extract_json_markdown_with_extra_spaces():
    text = "```json   \n{\"a\": 1}   \n```"
    expected = "{\"a\": 1}"
    assert extract_json_from_text(text) == expected

def test_extract_json_no_json():
    text = "No json here."
    assert extract_json_from_text(text) is None

def test_extract_json_nested_braces():
    text = "Some text before {\"outer\": {\"inner\": 1}} some text after"
    expected = "{\"outer\": {\"inner\": 1}}"
    assert extract_json_from_text(text) == expected

def test_extract_json_malformed_braces():
    # Only opening brace
    assert extract_json_from_text("This { has no end") is None
    # Only closing brace
    assert extract_json_from_text("This } has no start") is None

def test_extract_json_multiple_blocks():
    # Currently it takes the first match for ```json
    text = "```json\n{\"first\": 1}\n```\n```json\n{\"second\": 2}\n```"
    assert extract_json_from_text(text) == "{\"first\": 1}"

def test_extract_json_fallback_with_extra_text():
    # Test fallback when ```json is missing but braces are present
    text = "Intro { \"key\": \"value\" } Outro"
    assert extract_json_from_text(text) == "{ \"key\": \"value\" }"

def test_extract_json_greedy_fallback():
    # Current implementation is greedy, it might include non-JSON text if there are multiple pairs
    text = "First pair {not json} second pair {\"is\": \"json\"}"
    # current behavior would return "{not json} second pair {\"is\": \"json\"}"
    # Ideally it should probably return the valid JSON one, but the current logic is simple.
    result = extract_json_from_text(text)
    assert result == "{not json} second pair {\"is\": \"json\"}"
