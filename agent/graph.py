import logging
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from core.llm_router import router, LLMLayer
from core.utils import (
    normalize_term, 
    parse_frontmatter, 
    is_technical_term, 
    auto_link_concepts, 
    get_all_concepts, 
    parse_and_filter_concepts
)
from ingestion.docling_parser import DoclingParser
from retrieval.qdrant_store import QdrantHybridStore
from output.obsidian_writer import ObsidianWriter
from core.schemas import WikiPageSchema, WikiMetadataSchema, UpdateDecisionSchema
from core.prompts import (
    get_ingest_prompt,
    get_lint_body_prompt,
    get_metadata_prompt,
    get_fallback_prompt,
    get_translation_prompt,
    get_judgment_prompt,
    get_refine_prompt,
    get_draft_body_prompt
)

logger = logging.getLogger(__name__)

def extract_json_from_text(text: str) -> Optional[str]:
    """MarkdownなどのテキストからJSONブロックを抽出する。"""
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return text[start:end+1]
    return None

# シングルトン
docling_parser = DoclingParser()
qdrant_store = QdrantHybridStore()
obsidian_writer = ObsidianWriter()

def ingest_node(state: AgentState) -> Dict[str, Any]:
    """入力ファイルをパースし、最適なWikiページ名を提案。"""
    file_path = Path(state['input_file'])
    output_path = docling_parser.convert(str(file_path))
    if not output_path: return {"status": "error"}
    content = output_path.read_text(encoding="utf-8")
    
    llm = router.get_model(LLMLayer.L1)
    prompt = get_ingest_prompt(content[:1000])
    try:
        base_name = llm.invoke(prompt).content.strip()
        suggested_name = normalize_term(base_name)
        counter = 1
        while (obsidian_writer.wiki_dir / f"{suggested_name}.md").exists():
            suggested_name = f"{base_name}_{counter}"; counter += 1
    except: suggested_name = normalize_term(file_path.stem)

    retrieved = qdrant_store.search(content[:1000], k=5)
    return {
        "raw_markdown": content, 
        "target_page": suggested_name, 
        "source_filename": file_path.name, 
        "retrieved_docs": retrieved,
        "status": "ingested"
    }

def _find_red_links(wiki_dir: Path) -> Set[str]:
    pages = list(wiki_dir.rglob("*.md"))
    existing_normalized_names = {normalize_term(p.stem) for p in pages}
    red_links = set()
    for p in pages:
        if "raw_markdown" in str(p) or "sources" in str(p): continue
        try:
            content = p.read_text(encoding="utf-8")
            links = re.findall(r"\[\[(.*?)\]\]", content)
            for link in links:
                term = link.split("|")[0].strip().strip("[]")
                if not term or "/" in term or term == "Home": continue
                if ":" in term: continue
                norm_term = normalize_term(term)
                if not is_technical_term(term) or not is_technical_term(norm_term): continue
                if norm_term not in existing_normalized_names:
                    red_links.add(term)
        except Exception as e:
            logger.error(f"Error reading {p}: {e}")
    return red_links

def _fetch_context(term: str, llm) -> tuple[str, list, list]:
    search_query = term
    evidences = [d for d in qdrant_store.search(search_query, k=10) if d.metadata.get("type") in ["raw_source", "raw_markdown", "wiki_page"]]
    def evidence_priority(d):
        text = d.page_content
        return 0 if re.search(r'[ぁ-んァ-ヶ亜-熙]', text) else 1
    evidences = sorted(evidences, key=evidence_priority)

    if (not evidences or evidence_priority(evidences[0]) == 1) and re.search(r'[ぁ-んァ-ヶ亜-熙]', term):
        translation_prompt = get_translation_prompt(term)
        english_term = llm.invoke(translation_prompt).content.strip()
        logger.info(f"日本語用語 '{term}' を '{english_term}' として再検索します")
        evidences = [d for d in qdrant_store.search(english_term, k=8) if d.metadata.get("type") == "raw_source"]

    if evidences:
        sources = list(set([d.metadata.get('source') for d in evidences if d.metadata.get('source')]))
        source_links = [f"[[sources/{s}]]" for s in sources]
        context = "\n\n".join([f"Source: {d.metadata.get('source')}\n{d.page_content}" for d in evidences])
    else:
        sources = []
        source_links = ["LLM_Internal_Knowledge"]
        context = f"No specific context found in Qdrant. Please generate a stub page using your internal knowledge about '{term}'."
    return context, sources, source_links

def _generate_stub_data(term: str, context: str, source_links: list, evidences: list, llm) -> dict:
    body_prompt = get_lint_body_prompt(term, context)
    body_text = llm.invoke(body_prompt).content
    _, clean_body = parse_frontmatter(body_text)
    if not clean_body.strip(): clean_body = body_text

    metadata_prompt = get_metadata_prompt(clean_body, term)
    try:
        metadata = None
        try:
            metadata_llm = llm.with_structured_output(WikiMetadataSchema)
            metadata = metadata_llm.invoke(metadata_prompt)
        except Exception as se:
            logger.warning(f"Structured output failed in lint_node: {se}. Trying manual JSON extraction.")
            raw_res = llm.invoke(metadata_prompt).content
            json_str = extract_json_from_text(raw_res)
            if json_str:
                metadata = WikiMetadataSchema(**json.loads(json_str))
        if not metadata: raise ValueError("Could not extract metadata as JSON")
        global_concepts = get_all_concepts()
        all_targets = list(set(metadata.concepts + global_concepts))
        final_body = auto_link_concepts(clean_body, all_targets)
        filtered_concepts = [c for c in metadata.concepts if c.lower() not in ["用語名", "title", "abstract", "concept"]]
        data = {
            "title": metadata.title.strip().replace("[[", "").replace("]]", ""),
            "abstract": metadata.abstract,
            "concepts": filtered_concepts,
            "body": final_body,
            "tags": metadata.tags,
            "aliases": metadata.aliases or []
        }
    except Exception as e:
        logger.warning(f"Metadata extraction failed in lint_node for {term}: {e}")
        fallback_prompt = get_fallback_prompt(clean_body)
        try:
            raw_concepts = llm.invoke(fallback_prompt).content
            new_concepts = parse_and_filter_concepts(raw_concepts)
        except Exception as e2:
            logger.warning(f"Fallback LLM extraction failed: {e2}")
            new_concepts = []
        found_links = list(set(re.findall(r"\[\[(.*?)\]\]", clean_body)))
        link_concepts = [l.split("|")[0].strip().replace("[[", "").replace("]]", "") for l in found_links]
        global_concepts = get_all_concepts()
        concepts = list(set(new_concepts + link_concepts + global_concepts))
        tags = ["auto-draft"] + [c for c in new_concepts if len(c) <= 15 and " " not in c][:5]
        final_body = auto_link_concepts(clean_body, concepts)
        data = {
            "title": term.strip().replace("[[", "").replace("]]", ""),
            "abstract": "自動生成スタブ",
            "concepts": concepts,
            "body": final_body,
            "tags": tags,
            "aliases": []
        }

    data["sources"] = list(set(data.get("sources", []) + source_links))
    if not evidences: data["tags"] = list(set(data.get("tags", []) + ["stub"]))
    return data

def lint_node(state: AgentState) -> Dict[str, Any]:
    """Wiki内のRed-link（未作成ページへのリンク）を検知し、自動執筆する。"""
    logger.info("--- LINTING & AUTONOMOUS REPAIR ---")
    red_links = _find_red_links(obsidian_writer.wiki_dir)
    if not red_links: return {"status": "linted"}

    llm = router.get_model(LLMLayer.L2)
    def link_priority(t): return (0 if re.search(r'[ぁ-んァ-ヶ亜-熙]', t) else 1, t.lower())

    for term in sorted(list(red_links), key=link_priority)[:10]: 
        context, sources, source_links = _fetch_context(term, llm)
        evidences = [1] if sources else [] # mock for evidences presence
        data = _generate_stub_data(term, context, source_links, evidences, llm)
        try:
            obsidian_writer.create_draft_from_schema(data, sub_dir="concepts")
            logger.info(f"自動ドラフト作成: [[{term}]] (Sources: {len(sources)})")
        except Exception as e:
            logger.error(f"Failed to save concept for {term}: {e}")
    
    obsidian_writer.update_index()
    return {"status": "linted"}

def judgment_node(state: AgentState) -> Dict[str, Any]:
    """更新が必要か判定。"""
    llm = router.get_model(LLMLayer.L2)
    structured_llm = llm.with_structured_output(UpdateDecisionSchema)
    prompt = get_judgment_prompt(state['target_page'], state['raw_markdown'])
    try:
        result = structured_llm.invoke(prompt)
        logger.info(f"Update Decision for {state['target_page']}: {result.update_needed} (Reason: {result.reason})")
        return {"status": "update_needed" if result.update_needed else "ignored"}
    except Exception as e:
        logger.error(f"Judgment failed, defaulting to ignored: {e}")
        return {"status": "ignored"}

def refine_node(state: AgentState) -> Dict[str, Any]:
    """既存ページの洗練（構造化データ生成）。"""
    llm = router.get_model(LLMLayer.L2)
    structured_llm = llm.with_structured_output(WikiPageSchema)
    lang_inst = router.get_language_instruction()
    safe_name = normalize_term(state['target_page'])
    wiki_path = obsidian_writer.wiki_dir / f"{safe_name}.md"
    current = wiki_path.read_text(encoding="utf-8") if wiki_path.exists() else ""
    
    prompt = get_refine_prompt(state['target_page'], current, state['raw_markdown'], lang_inst)
    try:
        result = structured_llm.invoke(prompt)
        return {"proposed_data": result.model_dump(), "status": "refined"}
    except Exception as e:
        logger.warning(f"Structured output failed for refine_node: {e}. Falling back to text.")
        raw_text = llm.invoke(prompt).content
        fallback_data = {
            "title": state['target_page'],
            "abstract": "更新されたコンテンツ（自動抽出失敗）",
            "concepts": [],
            "body": raw_text,
            "tags": ["auto-updated"],
            "aliases": []
        }
        return {"proposed_data": fallback_data, "status": "refined"}

def draft_node(state: AgentState) -> Dict[str, Any]:
    """新規Wikiドラフト作成。"""
    llm = router.get_model(LLMLayer.L2)
    context = "\n\n".join([f"Source: {d.metadata.get('source')}\n{d.page_content}" for d in state["retrieved_docs"]])
    
    body_prompt = get_draft_body_prompt(state['target_page'], state['raw_markdown'], context)
    body_text = llm.invoke(body_prompt).content
    _, clean_body = parse_frontmatter(body_text)
    if not clean_body.strip(): clean_body = body_text
    
    metadata_prompt = get_metadata_prompt(clean_body, state['target_page'])
    try:
        metadata = None
        try:
            metadata_llm = llm.with_structured_output(WikiMetadataSchema)
            metadata = metadata_llm.invoke(metadata_prompt)
        except Exception as se:
            logger.warning(f"Structured output failed in draft_node: {se}. Trying manual JSON extraction.")
            raw_res = llm.invoke(metadata_prompt).content
            json_str = extract_json_from_text(raw_res)
            if json_str:
                metadata = WikiMetadataSchema(**json.loads(json_str))
        
        if not metadata: raise ValueError("Could not extract metadata as JSON")
        
        global_concepts = get_all_concepts()
        all_targets = list(set(metadata.concepts + global_concepts))
        final_body = auto_link_concepts(clean_body, all_targets)
        
        proposed_data = {
            "title": metadata.title.strip().replace("[[", "").replace("]]", ""),
            "abstract": metadata.abstract,
            "concepts": metadata.concepts,
            "body": final_body,
            "tags": metadata.tags,
            "aliases": metadata.aliases or [],
            "source_filename": state.get("source_filename"),
            "source_path": state.get("input_file"),
            "raw_markdown": state.get("raw_markdown")
        }
    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}. Extracting from text via fallback LLM.")
        fallback_prompt = get_fallback_prompt(clean_body)
        try:
            raw_concepts = llm.invoke(fallback_prompt).content
            new_concepts = parse_and_filter_concepts(raw_concepts)
        except Exception as e2:
            new_concepts = []

        found_links = list(set(re.findall(r"\[\[(.*?)\]\]", clean_body)))
        link_concepts = [l.split("|")[0].strip().replace("[[", "").replace("]]", "") for l in found_links]
        global_concepts = get_all_concepts()
        concepts = list(set(new_concepts + link_concepts + global_concepts))
        
        tags = ["auto-draft"] + [c for c in new_concepts if len(c) <= 15 and " " not in c][:5]
        paragraphs = [p.strip() for p in clean_body.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        abstract = paragraphs[0][:200] if paragraphs else "自動生成"
        final_body = auto_link_concepts(clean_body, concepts)
        
        proposed_data = {
            "title": state['target_page'].strip().replace("[[", "").replace("]]", ""),
            "abstract": abstract,
            "concepts": concepts,
            "body": final_body,
            "tags": tags,
            "aliases": [],
            "source_filename": state.get("source_filename"),
            "source_path": state.get("input_file"),
            "raw_markdown": state.get("raw_markdown")
        }
    
    return {"proposed_data": proposed_data, "status": "drafted"}


def review_node(state: AgentState) -> Dict[str, Any]:
    """構造化データを受け取ってドラフトファイルを出力する。"""
    logger.info("🚀🚀🚀 REVIEW_NODE STARTED 🚀🚀🚀")
    data = state.get("proposed_data")
    if data:
        logger.info(f"📝 WRITING WIKI PAGE: {data.get('title')}")
        obsidian_writer.create_draft_from_schema(data)
    else:
        logger.error("❌ NO PROPOSED_DATA FOUND IN STATE")
    return {"status": "completed"}

def router_entry(state: AgentState):
    status = state.get("status")
    if status == "starting_lint": return "lint"
    if status == "starting_refine": return "judgment"
    if state.get("maintenance_topic"): return "synthesis" # 未実装だが必要なら
    return "ingest"

workflow = StateGraph(AgentState)
workflow.add_node("ingest", ingest_node)
workflow.add_node("lint", lint_node)
workflow.add_node("judgment", judgment_node)
workflow.add_node("refine", refine_node)
workflow.add_node("draft", draft_node)
workflow.add_node("review", review_node)

workflow.add_conditional_edges(START, router_entry)
workflow.add_conditional_edges("judgment", lambda s: "refine" if s.get("status") == "update_needed" else END)
workflow.add_conditional_edges("ingest", lambda s: "draft" if s.get("status") != "error" else END)
workflow.add_edge("refine", "review")
workflow.add_edge("draft", "review")
workflow.add_edge("review", END)

app = workflow.compile(checkpointer=MemorySaver())
