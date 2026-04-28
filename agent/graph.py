import logging
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
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
    prompt = f"""与えられたドキュメントの内容を分析し、Obsidianのファイル名として最も適切な日本語のタイトル（例：ベクトル検索の進化_2024）を1つ提案してください。
解説は一切不要です。タイトルのみを出力してください。
内容:
{content[:1000]}"""
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

def lint_node(state: AgentState) -> Dict[str, Any]:
    """Wiki内のRed-link（未作成ページへのリンク）を検知し、自動執筆する。"""
    logger.info("--- LINTING & AUTONOMOUS REPAIR ---")
    wiki_dir = obsidian_writer.wiki_dir
    pages = list(wiki_dir.rglob("*.md"))
    
    # 既存の全ページ名を正規化して取得
    existing_normalized_names = {normalize_term(p.stem) for p in pages}
    red_links = set()
    
    for p in pages:
        if "raw_markdown" in str(p) or "sources" in str(p): continue
        try:
            content = p.read_text(encoding="utf-8")
            # [[リンク]] 形式を抽出
            links = re.findall(r"\[\[(.*?)\]\]", content)
            for link in links:
                term = link.split("|")[0].strip().strip("[]")
                if not term or "/" in term or term == "Home": continue
                if ":" in term: continue  # Category:LLM 等のMediaWiki記法をスキップ
                
                norm_term = normalize_term(term)
                # 技術用語フィルタ（数字のみ、短すぎる、ストップワード等）
                if not is_technical_term(term) or not is_technical_term(norm_term): continue
                
                if norm_term not in existing_normalized_names:
                    red_links.add(term) # 表示名の方を保持
        except Exception as e:
            logger.error(f"Error reading {p}: {e}")
    
    if not red_links:
        return {"status": "linted"}

    llm = router.get_model(LLMLayer.L2)
    lang_inst = router.get_language_instruction()
    # 日本語を含む用語を優先的にソート
    def link_priority(t):
        has_ja = 0 if re.search(r'[ぁ-んァ-ヶ亜-熙]', t) else 1
        return (has_ja, t.lower())

    for term in sorted(list(red_links), key=link_priority)[:10]: 
        # 日本語の場合は英語名も推測して検索精度を上げる（簡易的）
        search_query = term
        if re.search(r'[ぁ-んァ-ヶ亜-熙]', term):
             # 翻訳用の軽いLLM呼び出しを検討しても良いが、まずはそのまま検索
             # ベクトル検索(OpenAI/Ollama)はマルチリンガル対応していることが多い
             pass

        # エビデンスの取得 (フィルターを緩和し、既存のWikiページも参考にできるようにする)
        evidences = [d for d in qdrant_store.search(search_query, k=10) if d.metadata.get("type") in ["raw_source", "raw_markdown", "wiki_page"]]
        
        # 日本語ソースを優先的に並び替え
        def evidence_priority(d):
            # 日本語が含まれているか、特定のソース名（raw_markdown由来等）を優先
            text = d.page_content
            has_ja = 0 if re.search(r'[ぁ-んァ-ヶ亜-熙]', text) else 1
            return has_ja

        evidences = sorted(evidences, key=evidence_priority)

        # エビデンスが全くない、または日本語エビデンスを求めているが英語しかない場合の翻訳再試行
        if (not evidences or evidence_priority(evidences[0]) == 1) and re.search(r'[ぁ-んァ-ヶ亜-熙]', term):
            translation_prompt = f"Translate the following technical term to English. Output ONLY the translated term: {term}"
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
            logger.info(f"エビデンスなし。内部知識でスタブを生成します: [[{term}]]")
            
        # プロンプトの構築
        body_prompt = f"""あなたは高度な技術知識を持つWiki管理者です。
技術用語 '{term}' について、専門的な解説記事をMarkdown形式で作成してください。

コンテキスト:
{context}

【執筆指針】
1. # {term} (タイトル)
2. > [!abstract] 要約
   その用語の定義、重要性、RAGやLLMの文脈での役割を3行以上で具体的に要約してください。
3. ## 概要 / 詳細
   提供されたコンテキスト、およびあなたの内部知識を用いて、正確かつ客観的に解説してください。
4. ## 関連概念 / リンク
   本文中の重要用語には積極的に `[[用語名]]` で内部リンクを付与し、最後に「関連概念」セクションを設けてください。

【注意】
- 「自動生成スタブ」や「要約なし」といったプレースホルダーは絶対に使用しないでください。
- 専門用語についてはオリジナルの英語表記を優先し、Obsidian Markdown に準拠してください。
- 出力は Markdown 本文のみとし、YAMLフロントマターは含めないでください。
"""

        body_text = llm.invoke(body_prompt).content
        _, clean_body = parse_frontmatter(body_text)
        if not clean_body.strip():
            clean_body = body_text

        metadata_prompt = f"""以下のWiki記事からメタデータを抽出せよ。

記事本文:
{clean_body}

【抽出ルール】
- title: 記事のタイトル（{term}）
- abstract: 3行程度の具体的な要約。
- concepts: 本文中の主要な技術用語、概念のリスト（15個程度）。
- tags: 分類タグのリスト（短く、スペースを含まない）。
- aliases: ページタイトル '{term}' の完全な「別名」または「略称」のみをリスト化してください。関連用語は含めないでください。
"""
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
            
            if not metadata:
                raise ValueError("Could not extract metadata as JSON")

            # グローバル索引と抽出概念を統合
            global_concepts = get_all_concepts()
            all_targets = list(set(metadata.concepts + global_concepts))
            final_body = auto_link_concepts(clean_body, all_targets)
            
            # 不要な概念を除外
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
            
            # フォールバック: LLMに箇条書きのリストを要求
            fallback_prompt = f"""以下のテキストから、研究分野（NLP / RAG / システムエンジニアリング）において定義が必要な、**専門的な技術用語、固有のアルゴリズム名、モデル名**のみを厳選して抽出せよ。
- 一般的な名詞や動詞、単なる英単語は除外すること。
- 論文の引用（et al. や年号）、括弧記号は含めないこと。
- 無理に多く抽出せず、本当に重要なものだけを10〜15個程度抽出すること。
- 以下の形式で、1行に1つずつ箇条書きで出力すること。

出力形式:
- 専門用語1
- 専門用語2

テキスト:
{clean_body}"""
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

        # 取得したソース情報をマージ
        data["sources"] = list(set(data.get("sources", []) + source_links))
        
        # スタブの場合はタグに 'stub' を追加
        if not evidences:
            data["tags"] = list(set(data.get("tags", []) + ["stub"]))
        
        try:
            obsidian_writer.create_draft_from_schema(data, sub_dir="concepts")
            logger.info(f"自動ドラフト作成: [[{term}]] (Sources: {len(sources)})")
        except Exception as e:
            logger.error(f"Failed to save concept for {term}: {e}")
    
    obsidian_writer.update_index()
    return {"status": "linted"}

from core.schemas import WikiPageSchema, UpdateDecisionSchema

def judgment_node(state: AgentState) -> Dict[str, Any]:
    """更新が必要か判定。"""
    llm = router.get_model(LLMLayer.L2)
    structured_llm = llm.with_structured_output(UpdateDecisionSchema)
    
    prompt = f"既存のWiki知識と新規情報を比較し、更新が必要か判定せよ。\nターゲット: {state['target_page']}\n新規情報: {state['raw_markdown']}"
    
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
    
    prompt = f"""既存のWikiページ [[{state['target_page']}]] を最新情報に基づいて更新・洗練せよ。{lang_inst}
既存の記述を尊重しつつ、新情報を論理的に統合すること。

現状のコンテンツ:
{current}

追加・更新すべき新情報:
{state['raw_markdown']}

【言語と表記の指針】
- 専門用語、技術概念（例：Self-RAG, Retrieval, Critique等）については、オリジナルの英語表記を優先してください。

【リンク付与のルール】
- 知識が網の目となるよう、本文中の重要な用語には積極的に `[[用語名]]` の形式で内部リンクを付与してください。
- 英語表記であっても、重要な概念であれば `[[Self-RAG]]` のようにリンクを作成してください。
"""
    try:
        result = structured_llm.invoke(prompt)
        return {"proposed_data": result.model_dump(), "status": "refined"}
    except Exception as e:
        logger.warning(f"Structured output failed for refine_node: {e}. Falling back to text.")
        raw_text = llm.invoke(prompt).content
        # 簡易的なフォールバックデータ
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
    """新規Wikiドラフト作成。
    
    2ステップ方式:
      Step 1: 自由形式で記事本文を生成（Markdown）— 常に成功する
      Step 2: 生成された本文からメタデータを構造化抽出（Pydantic）— 成功率が高い
    
    body は自由記述であり Pydantic で制約しない。
    tags/aliases/abstract 等のメタデータのみ Pydantic で構造化する。
    """
    llm = router.get_model(LLMLayer.L2)
    lang_inst = router.get_language_instruction()
    
    context = "\n\n".join([f"Source: {d.metadata.get('source')}\n{d.page_content}" for d in state["retrieved_docs"]])
    
    # ── Step 1: 自由形式で記事本文を生成 ──
    body_prompt = f"""あなたは高度なナレッジエンジニアです。以下の情報を統合し、最高品質のWiki記事を執筆せよ。

ターゲットタイトル: {state['target_page']}
新規情報 (Raw text): {state['raw_markdown']}
コンテキスト (既存知識):
{context}

【執筆の要件】
1. # {state['target_page']} (H1タイトル)
2. > [!abstract] 要約
   記事の核心的な内容、技術的背景、および意義を3行以上で具体的に要約してください。
3. 本文構成:
   - 専門用語（Self-RAG, Retrieval, Critique, LLM等）は英語表記を優先。
   - 重要な用語には積極的に `[[用語名]]` で内部リンクを付与してください。
   - 図、表、箇条書きを活用して、読みやすく構造化してください。

注意: 出力は Markdown 本文のみとし、YAMLフロントマターは含めないでください。
"""
    body_text = llm.invoke(body_prompt).content
    
    # YAML が混入していた場合はクレンジング
    _, clean_body = parse_frontmatter(body_text)
    if not clean_body.strip():
        clean_body = body_text
    
    # ── Step 2: メタデータを構造化抽出 ──
    metadata_prompt = f"""以下のWiki記事からメタデータを抽出せよ。

記事本文:
{clean_body}

【抽出ルール】
- title: 記事のタイトル
- abstract: 3行程度の具体的かつ詳細な要約。
- concepts: 本文中の主要な技術用語、固有名詞、概念のリスト（15個以上）。
- tags: 分類タグのリスト（短く、スペースを含まない）。
- aliases: タイトル '{state['target_page']}' の完全な「別名」または「略称」のみ。関連用語は含めないこと。
"""
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
        
        if not metadata:
            raise ValueError("Could not extract metadata as JSON")
        
        # 抽出された concepts + グローバル索引を用いて自動リンク化
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
        logger.info(f"Metadata extracted: title={metadata.title}, tags={metadata.tags}")
    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}. Extracting from text via fallback LLM.")
        
        # フォールバック: LLMに箇条書きのリストを要求
        fallback_prompt = f"""以下のテキストから、研究分野（NLP / RAG / システムエンジニアリング）において定義が必要な、**専門的な技術用語、固有のアルゴリズム名、モデル名**のみを厳選して抽出せよ。
- 一般的な名詞や動詞、単なる英単語は除外すること。
- 論文の引用（et al. や年号）、括弧記号は含めないこと。
- 無理に多く抽出せず、本当に重要なものだけを10〜15個程度抽出すること。
- 以下の形式で、1行に1つずつ箇条書きで出力すること。

出力形式:
- 専門用語1
- 専門用語2

テキスト:
{clean_body}"""
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
