import logging
import re
import json
import concurrent.futures
from pathlib import Path
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from core.llm_router import router, LLMLayer
from core.utils import (
    normalize_term, 
    parse_frontmatter, 
    dump_frontmatter,
    auto_link_concepts, 
    get_all_concepts, 
    parse_and_filter_concepts,
    extract_json_from_text,
    WIKI_LINK_RE,
    safe_get_content,
    find_red_links
)
from ingestion.docling_parser import DoclingParser
from retrieval.qdrant_store import QdrantHybridStore
from output.obsidian_writer import ObsidianWriter
from core.schemas import WikiMetadataSchema, DraftConfig
from core.prompts import (
    get_ingest_prompt,
    get_lint_body_prompt,
    get_metadata_prompt,
    get_fallback_prompt,
    get_translation_prompt,
    get_refine_prompt,
    get_draft_body_prompt,
    get_synthesis_prompt
)

logger = logging.getLogger(__name__)

# シングルトン（遅延初期化用）
_docling_parser = None
_qdrant_store = None
_obsidian_writer = None

def get_docling_parser():
    global _docling_parser
    if _docling_parser is None:
        _docling_parser = DoclingParser()
    return _docling_parser

def get_qdrant_store():
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantHybridStore()
    return _qdrant_store

def get_obsidian_writer():
    global _obsidian_writer
    if _obsidian_writer is None:
        _obsidian_writer = ObsidianWriter()
    return _obsidian_writer

def ingest_node(state: AgentState) -> Dict[str, Any]:
    """入力ファイルをパースし、最適なWikiページ名を提案。"""
    file_path = Path(state['input_file'])
    parser = get_docling_parser()
    output_path = parser.convert(str(file_path))
    if not output_path: return {"status": "error"}
    content = output_path.read_text(encoding="utf-8")
    
    llm = router.get_model(LLMLayer.L1)
    prompt = get_ingest_prompt(content[:1000])
    writer = get_obsidian_writer()
    try:
        base_name = llm.invoke(prompt).content.strip()
        suggested_name = normalize_term(base_name)
        counter = 1
        while (writer.wiki_dir / f"{suggested_name}.md").exists():
            suggested_name = f"{base_name}_{counter}"; counter += 1
    except: suggested_name = normalize_term(file_path.stem)

    store = get_qdrant_store()
    retrieved = store.search(content[:1000], k=5)
    return {
        "raw_markdown": content, 
        "target_page": suggested_name, 
        "source_filename": file_path.name, 
        "retrieved_docs": retrieved,
        "status": "ingested"
    }



def _format_context(term: str, evidences: list) -> tuple[str, list, list]:
    """証拠ドキュメントをWiki文脈用の形式に変換する。"""
    if evidences:
        sources = list(set([d.metadata.get('source') for d in evidences if d.metadata.get('source')]))
        source_links = [f"[[sources/{s}]]" for s in sources]
        context = "\n\n".join([f"Source: {d.metadata.get('source')}\n{d.page_content}" for d in evidences])
    else:
        sources = []
        source_links = ["LLM_Internal_Knowledge"]
        context = f"No specific context found in Qdrant. Please generate a stub page using your internal knowledge about '{term}'."
    return context, sources, source_links

def _fetch_context(term: str, llm) -> tuple[str, list, list]:
    search_query = term
    store = get_qdrant_store()
    evidences = [d for d in store.search(search_query, k=10) if d.metadata.get("type") in ["raw_source", "raw_markdown", "wiki_page"]]
    def evidence_priority(d):
        text = d.page_content
        return 0 if re.search(r'[ぁ-んァ-ヶ亜-熙]', text) else 1
    evidences = sorted(evidences, key=evidence_priority)

    if (not evidences or evidence_priority(evidences[0]) == 1) and re.search(r'[ぁ-んァ-ヶ亜-熙]', term):
        translation_prompt = get_translation_prompt(term)
        english_term = llm.invoke(translation_prompt).content.strip()
        logger.info(f"日本語用語 '{term}' を '{english_term}' として再検索します")
        evidences = [d for d in store.search(english_term, k=8) if d.metadata.get("type") == "raw_source"]

    return _format_context(term, evidences)

def _batch_fetch_context(terms: list[str], llm) -> dict[str, tuple[str, list, list]]:
    """複数の用語に対してコンテキストをバッチで取得する。"""
    if not terms:
        return {}

    store = get_qdrant_store()
    # 1. 最初のバッチ検索
    results1 = store.search_batch(terms, k=10)

    def get_evidence_priority(d):
        text = d.page_content
        return 0 if re.search(r'[ぁ-んァ-ヶ亜-熙]', text) else 1

    final_evidences = {}
    terms_needing_translation = []

    for term, docs in zip(terms, results1):
        evidences = [d for d in docs if d.metadata.get("type") in ["raw_source", "raw_markdown", "wiki_page"]]
        evidences = sorted(evidences, key=get_evidence_priority)

        if (not evidences or get_evidence_priority(evidences[0]) == 1) and re.search(r'[ぁ-んァ-ヶ亜-熙]', term):
            terms_needing_translation.append(term)
        else:
            final_evidences[term] = evidences

    # 2. 翻訳が必要な場合のバッチ処理
    if terms_needing_translation:
        prompts = [get_translation_prompt(t) for t in terms_needing_translation]
        translated_results = llm.batch(prompts)
        english_terms = [safe_get_content(res.content).strip() for res in translated_results]

        for t, eng in zip(terms_needing_translation, english_terms):
            logger.info(f"日本語用語 '{t}' を '{eng}' として再検索します")

        results2 = store.search_batch(english_terms, k=8)
        for t, docs in zip(terms_needing_translation, results2):
            final_evidences[t] = [d for d in docs if d.metadata.get("type") == "raw_source"]

    # 3. コンテキストの組み立て
    batch_context = {}
    for term in terms:
        evidences = final_evidences.get(term, [])
        batch_context[term] = _format_context(term, evidences)

    return batch_context

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
        writer = get_obsidian_writer()
        global_concepts = get_all_concepts(wiki_dir=writer.wiki_dir)
        all_targets = list(set(metadata.concepts + global_concepts))
        final_body = auto_link_concepts(clean_body, all_targets)
        filtered_concepts = [c for c in metadata.concepts if c.lower() not in ["用語名", "title", "abstract", "concept"]]
        data = {
            "title": normalize_term(metadata.title.strip().replace("[[", "").replace("]]", "")),
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
            raw_concepts = safe_get_content(llm.invoke(fallback_prompt).content)
            new_concepts = parse_and_filter_concepts(raw_concepts)
        except: new_concepts = []
        
        paragraphs = [p.strip() for p in clean_body.split("\n\n") if p.strip() and not p.strip().startswith("#") and not p.strip().startswith(">")]
        fallback_abstract = paragraphs[0][:200] if paragraphs else f"{term}に関する解説スタブ記事。"
        
        data = {
            "title": normalize_term(term.strip().replace("[[", "").replace("]]", "")),
            "abstract": fallback_abstract,
            "concepts": new_concepts,
            "body": clean_body,
            "tags": ["未審査"],
            "aliases": []
        }
    return data



def lint_node(state: AgentState) -> Dict[str, Any]:
    """孤立した赤リンク（未作成ページ）を特定し、言及頻度に基づいてスタブ記事を自動生成する。"""
    logger.info("🛠️ LINT_NODE STARTED 🛠️")
    writer = get_obsidian_writer()
    red_links_dict = find_red_links(writer.wiki_dir)
    if not red_links_dict: return {"status": "linted"}

    llm = router.get_model(LLMLayer.L1)
    # 重複を避けるために現在の concepts フォルダの中身も考慮
    existing_concepts = {normalize_term(p.stem) for p in (writer.wiki_dir / "concepts").glob("*.md")}

    # 言及頻度順（降順）にソート
    sorted_red_links = sorted(red_links_dict.items(), key=lambda x: x[1], reverse=True)
    
    # 処理対象の用語を最大50個まで抽出（言及頻度順にソートされたものから）
    targets = []
    for term, frequency in sorted_red_links:
        if normalize_term(term) not in existing_concepts:
            targets.append(term)
        if len(targets) >= 50:
            break

    if not targets:
        return {"status": "linted"}

    # バッチでコンテキストを取得 (N+1クエリを回避)
    batch_contexts = _batch_fetch_context(targets, llm)

    def _process_term_optimized(term):
        try:
            frequency = red_links_dict.get(term, 0)
            logger.info(f"🔍 Generating stub for: {term} (mentions: {frequency})")
            # 事前取得したコンテキストを使用
            context, sources, source_links = batch_contexts[term]
            data = _generate_stub_data(term, context, source_links, [], llm)
            # スタブ作成
            writer.create_draft_from_schema(data, sub_dir="concepts")
            return True
        except Exception as e:
            logger.error(f"Error generating stub for {term}: {e}")
            return False

    # スレッドプールを使用して並列処理 (I/OバウンドなLLM生成呼び出しを高速化)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(_process_term_optimized, targets))
    
    return {"status": "linted"}

def draft_node(state: AgentState) -> Dict[str, Any]:
    """取り込んだ文書から、Wiki記事の草案（本文とメタデータ）を生成。"""
    logger.info("✍️ DRAFT_NODE STARTED ✍️")
    llm = router.get_model(LLMLayer.L2)
    
    target_page = state['target_page']
    raw_md = state['raw_markdown']
    context = "\n\n".join([d.page_content for d in state.get('retrieved_docs', [])])
    
    prompt = get_draft_body_prompt(target_page, raw_md, context)
    
    try:
        # 構造化出力を優先
        structured_llm = llm.with_structured_output(WikiMetadataSchema)
        proposed_data = structured_llm.invoke(prompt)
        proposed_content = proposed_data.generate_markdown()
    except Exception as e:
        logger.warning(f"Structured output failed in draft_node: {e}. Trying manual JSON extraction.")
        res = llm.invoke(prompt).content
        json_str = extract_json_from_text(res)
        if json_str:
            try:
                proposed_data = WikiMetadataSchema.model_validate_json(json_str)
                proposed_content = proposed_data.generate_markdown()
            except: proposed_content = res
        else: proposed_content = res

    return {"proposed_content": proposed_content, "status": "drafted"}

def refine_node(state: AgentState) -> Dict[str, Any]:
    """既存のWikiページを最新情報に基づいて洗練させる。"""
    logger.info("✨ REFINE_NODE STARTED ✨")
    llm = router.get_model(LLMLayer.L2)
    lang_inst = router.get_language_instruction()
    writer = get_obsidian_writer()
    
    target = state['target_page']
    current = writer.read_page(target) or ""
    diff = state['raw_markdown'] # Refine時はdiffがここに入る
    
    prompt = get_refine_prompt(target, current, diff, lang_inst)
    
    try:
        result = structured_llm.invoke(prompt)
        proposed_data = result.model_dump()
        proposed_data["title"] = normalize_term(proposed_data.get("title") or state['target_page'])
        return {"proposed_data": proposed_data, "status": "refined"}
    except Exception as e:
        logger.warning(f"Structured output failed for refine_node: {e}. Falling back to text.")
        raw_text = safe_get_content(llm.invoke(prompt).content)
        fallback_data = {
            "title": normalize_term(state['target_page']),
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
    body_text = safe_get_content(llm.invoke(body_prompt).content)
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
            raw_res = safe_get_content(llm.invoke(metadata_prompt).content)
            json_str = extract_json_from_text(raw_res)
            if json_str:
                metadata = WikiMetadataSchema(**json.loads(json_str))
        
        if not metadata: raise ValueError("Could not extract metadata as JSON")
        
        global_concepts = get_all_concepts()
        all_targets = list(set(metadata.concepts + global_concepts))
        final_body = auto_link_concepts(clean_body, all_targets)
        
        proposed_data = {
            "title": normalize_term(metadata.title.strip().replace("[[", "").replace("]]", "")),
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
            raw_concepts = safe_get_content(llm.invoke(fallback_prompt).content)
            new_concepts = parse_and_filter_concepts(raw_concepts)
        except Exception:
            new_concepts = []

        found_links = list(set(WIKI_LINK_RE.findall(clean_body)))
        link_concepts = [l.split("|")[0].strip().replace("[[", "").replace("]]", "") for l in found_links]
        global_concepts = get_all_concepts()
        concepts = list(set(new_concepts + link_concepts + global_concepts))
        
        tags = ["auto-draft"] + [c for c in new_concepts if len(c) <= 15 and " " not in c][:5]
        paragraphs = [p.strip() for p in clean_body.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        abstract = paragraphs[0][:200] if paragraphs else "自動生成"
        final_body = auto_link_concepts(clean_body, concepts)
        
        proposed_data = {
            "title": normalize_term(state['target_page'].strip().replace("[[", "").replace("]]", "")),
            "abstract": abstract,
            "concepts": concepts,
            "body": final_body,
            "tags": tags,
            "aliases": [],
            "source_filename": state.get("source_filename"),
            "source_path": state.get("input_file"),
            "raw_markdown": state.get("raw_markdown")
        }
    
    # proposed_data から proposed_content を組み立てる
    metadata_fm = {
        "type": "Article",
        "tags": proposed_data.get("tags", []),
        "aliases": proposed_data.get("aliases", []),
        "concepts": proposed_data.get("concepts", []),
        "description": proposed_data.get("abstract", "")
    }
    if proposed_data.get("source_filename"):
        metadata_fm["sources"] = [f"[[sources/{proposed_data.get('source_filename')}]]"]
        
    concepts_str = "\n".join([f"- {c}" for c in proposed_data.get("concepts", [])])
    
    final_body_md = f"""# {proposed_data['title']}

> [!abstract] 要約
> {proposed_data['abstract']}

{proposed_data['body']}

## 💡 主要な概念
{concepts_str}
"""
    proposed_content = f"{dump_frontmatter(metadata_fm)}\n\n{final_body_md.strip()}"
    
    return {"proposed_data": proposed_data, "proposed_content": proposed_content, "status": "drafted"}

def conflict_node(state: AgentState) -> Dict[str, Any]:
    """コンフリクトマーカーが含まれるドキュメントを整理・解消する。"""
    logger.info("⚔️ CONFLICT_NODE STARTED ⚔️")
    llm = router.get_model(LLMLayer.L2)
    
    target = state['target_page']
    content_with_conflicts = state['raw_markdown']
    
    # コンフリクト解消用プロンプト（Draftプロンプトを流用しつつ文脈を補足）
    prompt = get_draft_body_prompt(
        target, 
        content_with_conflicts, 
        "注意: このコンテンツにはGitコンフリクトマーカー (<<<<<<<, =======, >>>>>>>) が含まれています。これらを解消し、最も合理的な形に統合してください。"
    )
    
    try:
        structured_llm = llm.with_structured_output(WikiMetadataSchema)
        proposed_data = structured_llm.invoke(prompt)
        proposed_content = proposed_data.generate_markdown()
    except Exception as e:
        logger.warning(f"Structured output failed in conflict_node: {e}.")
        res = safe_get_content(llm.invoke(prompt).content)
        proposed_content = res

    return {"proposed_content": proposed_content, "status": "resolved"}

def review_node(state: AgentState) -> Dict[str, Any]:
    """生成されたコンテンツをレビュー用にファイル出力。"""
    logger.info("🎨 REVIEW_NODE STARTED 🎨")
    target = state['target_page']
    content = state['proposed_content']
    
    input_path = state.get("input_file")
    raw_md = state.get("raw_markdown")

    writer = get_obsidian_writer()
    # レビュー用ファイルの作成 (ソース情報も引き継ぐ)
    save_path = writer.create_draft_file(DraftConfig(
        page_name=target,
        proposed_content=content,
        source_filename=Path(input_path).name if input_path else None,
        source_path=input_path,
        raw_markdown=raw_md
    ))
    logger.info(f"📝 Review draft created: {save_path}")
    
    return {"target_page": target, "proposed_content": content, "status": "reviewed"}

def synthesis_node(state: AgentState) -> Dict[str, Any]:
    """メンテナンス対象のトピックについて、関連情報を統合してWiki記事を生成。"""
    logger.info("🧠 SYNTHESIS_NODE STARTED 🧠")
    llm = router.get_model(LLMLayer.L2)
    topic = state['maintenance_topic']

    # 関連情報の検索
    store = get_qdrant_store()
    retrieved = store.search(topic, k=15)
    context = "\n\n".join([f"Source: {d.metadata.get('source')}\n{d.page_content}" for d in retrieved])

    # コンテンツ生成
    synthesis_prompt = get_synthesis_prompt(topic, context)
    body_text = safe_get_content(llm.invoke(synthesis_prompt).content)
    _, clean_body = parse_frontmatter(body_text)
    if not clean_body.strip(): clean_body = body_text

    # メタデータ抽出
    metadata_prompt = get_metadata_prompt(clean_body, topic)
    try:
        metadata = None
        try:
            metadata_llm = llm.with_structured_output(WikiMetadataSchema)
            metadata = metadata_llm.invoke(metadata_prompt)
        except Exception as se:
            logger.warning(f"Structured output failed in synthesis_node: {se}. Trying manual JSON extraction.")
            raw_res = safe_get_content(llm.invoke(metadata_prompt).content)
            json_str = extract_json_from_text(raw_res)
            if json_str:
                metadata = WikiMetadataSchema(**json.loads(json_str))

        if not metadata: raise ValueError("Could not extract metadata as JSON")

        global_concepts = get_all_concepts()
        all_targets = list(set(metadata.concepts + global_concepts))
        final_body = auto_link_concepts(clean_body, all_targets)

        proposed_data = {
            "title": normalize_term(metadata.title.strip().replace("[[", "").replace("]]", "")),
            "abstract": metadata.description,
            "concepts": metadata.concepts,
            "body": final_body,
            "tags": metadata.tags + ["maintenance"],
            "aliases": metadata.aliases or []
        }
    except Exception as e:
        logger.warning(f"Metadata extraction failed in synthesis_node: {e}")
        proposed_data = {
            "title": normalize_term(topic),
            "abstract": "自動生成された統合記事（メタデータ抽出失敗）",
            "concepts": [],
            "body": clean_body,
            "tags": ["maintenance", "auto-generated"],
            "aliases": []
        }

    # proposed_content を組み立てる
    metadata_fm = {
        "type": "Article",
        "tags": proposed_data.get("tags", []),
        "aliases": proposed_data.get("aliases", []),
        "concepts": proposed_data.get("concepts", []),
        "description": proposed_data.get("abstract", "")
    }
    concepts_str = "\n".join([f"- {c}" for c in proposed_data.get("concepts", [])])
    final_body_md = f"# {proposed_data['title']}\n\n> [!abstract] 要約\n> {proposed_data['abstract']}\n\n{proposed_data['body']}\n\n## 💡 主要な概念\n{concepts_str}"
    proposed_content = f"{dump_frontmatter(metadata_fm)}\n\n{final_body_md.strip()}"

    return {
        "proposed_data": proposed_data,
        "proposed_content": proposed_content,
        "target_page": proposed_data["title"],
        "status": "synthesized"
    }

# グラフ構成
workflow = StateGraph(AgentState)

workflow.add_node("ingest", ingest_node)
workflow.add_node("lint", lint_node)
workflow.add_node("draft", draft_node)
workflow.add_node("refine", refine_node)
workflow.add_node("conflict", conflict_node)
workflow.add_node("synthesis", synthesis_node)
workflow.add_node("review", review_node)

# 条件付き遷移や他のエントリーポイント
def route_lint(state: AgentState):
    # status が linted かつ 元の入力に maintenance_topic や input_file がない場合は終了
    # ただし、現状は starting_lint というフラグで判別するのが確実
    if state.get("status") == "linted" and not state.get("input_file") and not state.get("maintenance_topic"):
        return END
    return "review"

def route_start(state: AgentState):
    if state.get("maintenance_topic"):
        return "synthesis"
    if state.get("status") == "starting_refine":
        return "refine"
    if state.get("status") == "starting_conflict":
        return "conflict"
    if state.get("status") == "starting_lint":
        return "lint"
    return "ingest"

workflow.add_conditional_edges(START, route_start)
workflow.add_edge("ingest", "draft")
workflow.add_edge("draft", "lint")
workflow.add_conditional_edges("lint", route_lint, {"review": "review", END: END})
workflow.add_edge("refine", "review")
workflow.add_edge("conflict", "review")
workflow.add_edge("synthesis", "review")
workflow.add_edge("review", END)

app = workflow.compile(checkpointer=MemorySaver(), interrupt_before=["review"])
