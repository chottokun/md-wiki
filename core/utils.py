import re
import unicodedata
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from ruamel.yaml import YAML
from io import StringIO
from functools import lru_cache

# YAMLハンドラーの初期化 (コメントとスタイルを維持)
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# 各種ハイフン・ダッシュ類を標準ハイフンに統一するための変換テーブル
# (\u2010-\u2015, \uFE58, \uFE63, \uFF0D など)
DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\uFE58\uFE63\uFF0D"
DASH_TRANSLATE_TABLE = str.maketrans(DASH_CHARS, "-" * len(DASH_CHARS))

@lru_cache(maxsize=2048)
def normalize_term(term: str) -> str:
    """
    Wiki全体で共通の用語正規化ロジック。
    1. Unicode正規化 (NFKC)
    2. スペースをアンダースコアに統一
    3. 各種ハイフン・ダッシュを標準ハイフンに統一
    4. 全角括弧を半角に
    5. 小文字化 (オプション: 英語の場合のみ)
    """
    if not term:
        return ""
    
    # Unicode正規化 (全角英数→半角、互換文字の統一)
    t = unicodedata.normalize("NFKC", term)
    
    # 各種ハイフン・ダッシュ類を ASCII ハイフンに統一
    t = t.translate(DASH_TRANSLATE_TABLE)
    
    # 全角括弧→半角
    t = t.replace('（', '(').replace('）', ')')
    
    # スラッシュやバックスラッシュをアンダースコアに置換（パス構成を回避）
    t = t.replace('/', '_').replace('\\', '_')

    # コロン（MediaWiki名前空間記法）を除去
    t = t.replace(':', '')
    
    # トリムを最初に行う
    t = t.strip()
    
    # スペースをアンダースコアに置換し、連続するアンダースコアを1つに
    t = t.replace(" ", "_")
    t = re.sub(r'_+', '_', t)
    
    # 小文字化
    t = t.lower()
    
    # 拡張子の削除
    t = re.sub(r'\.md$', '', t)
    
    return t

def parse_frontmatter(content: str) -> tuple[Optional[Dict[str, Any]], str]:
    """
    MarkdownからYAMLフロントマターと本文を分離してパースする。
    """
    content = content.strip()
    # 末尾の改行があってもなくてもマッチするように修正
    match = re.search(r"^---\s*\n(.*?)\n---\s*(\n|$)", content, re.DOTALL)
    if match:
        fm_text = match.group(1)
        body = content[match.end():].strip()
        try:
            data = yaml.load(fm_text)
            return dict(data) if data else {}, body
        except Exception:
            return None, content
    return None, content

def dump_frontmatter(data: Dict[str, Any]) -> str:
    """
    データをYAMLフロントマター形式の文字列に変換する。
    """
    stream = StringIO()
    yaml.dump(data, stream)
    return f"---\n{stream.getvalue().strip()}\n---\n"

@lru_cache(maxsize=1)
def _get_all_concepts_internal(wiki_dir: str) -> List[str]:
    """内部用キャッシュ関数"""
    concept_dir = Path(wiki_dir) / "concepts"
    if not concept_dir.exists():
        return []
    concepts = []
    for f in concept_dir.glob("*.md"):
        name = f.stem
        # 不要な記号の除去
        name = name.strip().replace("[[", "").replace("]]", "")
        if name:
            concepts.append(name)
    return list(set(concepts))

def get_all_concepts(wiki_dir: str = "wiki") -> List[str]:
    """wiki/concepts ディレクトリ内のファイル名から既存の概念リストを取得する。
    
    呼び出し側での変更がキャッシュに影響しないよう、常にコピーを返す。
    """
    return list(_get_all_concepts_internal(str(wiki_dir)))

WIKI_LINK_RE = re.compile(r"\[\[([^|#\]]+)(?:[|#][^\]]+)?\]\]")

def auto_link_concepts(body: str, concepts: List[str]) -> str:
    """本文中の用語を自動でリンク化する。
    
    コードブロックや見出し、すでにリンク化されている箇所を回避し、
    最も長い用語から優先的にリンクを付与する。
    """
    if not concepts or not body:
        return body

    # ハイフンの正規化 (各種ダッシュを標準ハイフンに)
    body = body.translate(DASH_TRANSLATE_TABLE)
    normalized_concepts = [c.translate(DASH_TRANSLATE_TABLE) for c in concepts]

    placeholders = {}
    
    # 1. コードブロックの退避
    def code_repl(match):
        ph = f"__CODE_BLOCK_{uuid.uuid4().hex}__"
        placeholders[ph] = match.group(0)
        return ph
    body = re.sub(r"```.*?```", code_repl, body, flags=re.DOTALL)
    
    # 2. 見出しの退避
    def header_repl(match):
        ph = f"__HEADER_{uuid.uuid4().hex}__"
        placeholders[ph] = match.group(0)
        return ph
    body = re.sub(r"^#+ .*$", header_repl, body, flags=re.MULTILINE)

    # 3. 既存リンクの退避 (二重リンク防止)
    def link_repl(match):
        ph = f"__LINK_{uuid.uuid4().hex}__"
        placeholders[ph] = match.group(0)
        return ph
    body = re.sub(r"\[\[.*?\]\]", link_repl, body)
    
    # 用語の長い順にソート（最長一致を優先）
    sorted_concepts = sorted(list(set(normalized_concepts)), key=len, reverse=True)
    
    for concept in sorted_concepts:
        if len(concept) < 2: continue
        # 一般的すぎる用語やプレースホルダを除外
        if concept.lower() in ["用語名", "title", "abstract", "concept"]: continue

        escaped_concept = re.escape(concept)
        # 境界条件チェック: 前後に英数字やハイフンがない場合のみ置換
        pattern = rf"(?<![A-Za-z0-9_\-]){escaped_concept}(?![A-Za-z0-9_\-])"
        body = re.sub(pattern, f"[[{concept}]]", body)
        
        # リンク化したばかりの部分を即座に退避して、短い単語による重複置換を防ぐ
        def new_link_repl(match):
            ph = f"__LINK_{uuid.uuid4().hex}__"
            placeholders[ph] = match.group(0)
            return ph
        body = re.sub(rf"\[\[{escaped_concept}\]\]", new_link_repl, body)
    
    # 4. 退避した要素を戻す
    for ph, orig in placeholders.items():
        body = body.replace(ph, orig)
        
    return body.strip()

def parse_and_filter_concepts(raw_llm_output: str) -> List[str]:
    """LLMから出力された箇条書きの概念リストをパースし、ノイズを除去する。"""
    new_concepts = []
    for line in raw_llm_output.split("\n"):
        line = line.strip()
        if line.startswith("-"):
            c = line[1:].strip().strip(".,;:").replace("[[", "").replace("]]", "")
            if len(c) < 2: continue
            if ")" in c and "(" not in c: continue
            if "et al" in c.lower(): continue
            if c.lower() in ["用語名", "title", "abstract", "concept"]: continue
            new_concepts.append(c)
    return list(dict.fromkeys(new_concepts))

TECHNICAL_STOPWORDS = {
    "カント", "うつ病", "フィードバック", "ジャーナリング", "スコアリング", 
    "タイトル", "要約", "概要", "詳細", "目次", "参考文献", "謝辞",
    "background", "summary", "abstract", "title", "conclusion", "references",
    "introduction", "method", "results", "discussion", "future_work",
    "human", "people", "user", "study", "research", "paper", "article"
}

@lru_cache(maxsize=2048)
def is_technical_term(term: str) -> bool:
    """用語が技術的・専門的であるか判定する（簡易フィルタ）。"""
    if not term: return False
    norm = term.lower().strip()
    if norm in TECHNICAL_STOPWORDS: return False
    if len(norm) <= 1: return False
    if norm.isdigit(): return False
    # 特殊記号のみ、または特定の単語のみを排除
    if re.match(r'^[0-9\.\-\(\)\s]+$', norm): return False
    return True

def extract_json_from_text(text: str) -> Optional[str]:
    """
    MarkdownなどのテキストからJSONブロックを抽出する。
    1. ```json ... ``` ブロックを優先。
    2. 見つからない場合は、最初のバランスした { ... } を抽出。
    """
    if not text:
        return None
        
    # 1. ```json ... ``` の抽出
    # ブロックを見つけてから、その中をバランスチェックする
    json_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if json_block_match:
        inner = json_block_match.group(1)
        result = _extract_balanced_json(inner)
        if result:
            return result
        
    # 2. 直接バランスしたブラケットを探す
    return _extract_balanced_json(text)

def _extract_balanced_json(text: str) -> Optional[str]:
    """最初に見つかった { から、対応する } までの範囲を抽出する。"""
    start = text.find("{")
    if start == -1:
        return None
        
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
                
    return None
