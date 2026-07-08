import os
import concurrent.futures
import re
import sys
import unicodedata
import uuid
from collections import Counter
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import ipaddress
from ruamel.yaml import YAML
from io import StringIO
from functools import lru_cache

# YAMLハンドラーの初期化 (コメントとスタイルを維持)
yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# セキュアなパース用のハンドラー (フロントマターのロードに使用)
_safe_yaml = YAML(typ='safe')

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

def _migrate_legacy_frontmatter(data: Dict[str, Any]) -> Dict[str, Any]:
    """レガシーフィールド名を OKF v0.1 準拠名にマイグレーションする。
    
    WikiFrontmatterSchema の model_validator と同等のロジックだが、
    スキーマを介さない直接的なフロントマター操作にも対応する。
    """
    if not data:
        return data
    # abstract → description
    if "abstract" in data and "description" not in data:
        data["description"] = data.pop("abstract")
    elif "abstract" in data and "description" in data:
        data.pop("abstract")
    # updated → timestamp
    if "updated" in data and "timestamp" not in data:
        data["timestamp"] = data.pop("updated")
    elif "updated" in data and "timestamp" in data:
        data.pop("updated")
    # type: wiki → type: Article
    if data.get("type") == "wiki":
        data["type"] = "Article"
    return data


def safe_get_content(content: Any) -> str:
    """
    LangChainのAIMessage.contentなど、リストや文字列で返ってくる値を一貫して文字列として取得する。
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
        return "".join(text_parts)
    elif content is None:
        return ""
    return str(content)


def parse_frontmatter(content: Any) -> tuple[Optional[Dict[str, Any]], str]:
    """
    MarkdownからYAMLフロントマターと本文を分離してパースする。
    レガシーフィールド名は OKF v0.1 準拠名に自動マイグレーションされる。
    """
    content = safe_get_content(content).strip()
    # 末尾の改行があってもなくてもマッチするように修正
    match = re.search(r"^---\s*\n(.*?)\n---\s*(\n|$)", content, re.DOTALL)
    if match:
        fm_text = match.group(1)
        body = content[match.end():].strip()
        try:
            data = _safe_yaml.load(fm_text)
            result = dict(data) if data else {}
            return _migrate_legacy_frontmatter(result), body
        except Exception:
            return None, content
    return None, content

# OKF v0.1 推奨フィールド順序: type → title → description → resource → tags → timestamp → 拡張
_OKF_FIELD_ORDER = [
    "type", "title", "description", "resource", "tags", "timestamp",
    # md-wiki extensions
    "aliases", "concepts", "created", "sources",
]

def dump_frontmatter(data: Dict[str, Any]) -> str:
    """
    データをYAMLフロントマター形式の文字列に変換する。
    OKF v0.1 準拠のフィールド順序で出力する。
    """
    # OKF フィールド順序に従ってソート
    ordered = {}
    for key in _OKF_FIELD_ORDER:
        if key in data:
            ordered[key] = data[key]
    # 残りのフィールド（producer-defined extensions）
    for key, val in data.items():
        if key not in ordered:
            ordered[key] = val
    
    stream = StringIO()
    yaml.dump(ordered, stream)
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
    "タイトル", "要約", "概要", "詳細", "目次", "参考文献", "謝辞", "home",
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

def is_safe_url(url: str) -> bool:
    """URLが安全か（SSRF対策）をチェックする。

    http/httpsのみ許可し、169.254.169.254などのリンクローカル・マルチキャストアドレスを拒否する。
    ただし、ローカルのOllama等に対応するため、localhostやループバックIPは許可する。
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname == "localhost":
            return True

        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_loopback:
                return True
            if ip.is_link_local or ip.is_multicast:
                return False
        except ValueError:
            # IPアドレスでない場合はドメイン名とみなす
            pass

        return True
    except Exception:
        return False

def setup_windows_utf8():
    """
    Windows環境においてコンソールのコードページをUTF-8に設定し、
    標準入出力およびサブプロセスのエンコーディングを強制する。
    """
    if sys.platform == "win32":
        # Windowsのコンソールコードページを UTF-8 (65001) に強制変更
        import ctypes
        try:
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
        # 環境変数でPythonサブプロセスにもUTF-8を強制
        os.environ["PYTHONUTF8"] = "1"
        os.environ["PYTHONIOENCODING"] = "utf-8"
        # 標準出力と標準エラーを UTF-8 に強制
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def _extract_balanced_json(text: str) -> Optional[str]:
    """最初に見つかった { から、対応する } までの範囲を抽出する。"""
    if text.count("{") != text.count("}"):
        return None
        
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

def find_red_links(wiki_dir: Path) -> Counter:
    """
    Wikiディレクトリを走査し、実体のないリンク（赤リンク）とその出現回数を集計する。
    並列処理により高速化されている。
    """
    # 予約ディレクトリとファイルをパスパーツで除外
    all_pages = list(wiki_dir.rglob("*.md"))
    pages = [
        p for p in all_pages
        if "raw_markdown" not in p.parts
        and "sources" not in p.parts
        and ".obsidian" not in p.parts
        and p.name != "Management Dashboard.md"
    ]

    existing_normalized_names = {normalize_term(p.stem) for p in pages}
    red_links_counter = Counter()

    def process_page(p: Path) -> Counter:
        local_counter = Counter()
        try:
            content = p.read_text(encoding="utf-8")
            links = WIKI_LINK_RE.findall(content)
            for term in links:
                term = term.strip().strip("[]")
                if not term or "/" in term or "\\" in term: continue
                if term.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.gif')): continue
                if ":" in term: continue

                norm_term = normalize_term(term)
                if not is_technical_term(term) or not is_technical_term(norm_term): continue

                if norm_term not in existing_normalized_names:
                    local_counter[term] += 1
        except Exception:
            pass
        return local_counter

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_page, p) for p in pages]
        for future in concurrent.futures.as_completed(futures):
            red_links_counter.update(future.result())

    return red_links_counter
