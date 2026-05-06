def get_ingest_prompt(content: str) -> str:
    return f"""与えられたドキュメントの内容を分析し、Obsidianのファイル名として最も適切な日本語のタイトル（例：ベクトル検索の進化_2024）を1つ提案してください。
解説は一切不要です。タイトルのみを出力してください。
内容:
{content}"""

def get_lint_body_prompt(term: str, context: str) -> str:
    return f"""あなたは高度な技術知識を持つWiki管理者です。
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

def get_metadata_prompt(body: str, title_or_term: str) -> str:
    return f"""以下のWiki記事からメタデータを抽出せよ。

記事本文:
{body}

【抽出ルール】
- title: 記事のタイトル（{title_or_term}）
- abstract: 3行程度の具体的かつ詳細な要約。
- concepts: 本文中の主要な技術用語、固有名詞、概念のリスト（15個程度）。
- tags: 分類タグのリスト（短く、スペースを含まない）。
- aliases: ページタイトル '{title_or_term}' の完全な「別名」または「略称」のみをリスト化してください。関連用語は含めないでください。
"""

def get_fallback_prompt(body: str) -> str:
    return f"""以下のテキストから、研究分野（NLP / RAG / システムエンジニアリング）において定義が必要な、**専門的な技術用語、固有のアルゴリズム名、モデル名**のみを厳選して抽出せよ。
- 一般的な名詞や動詞、単なる英単語は除外すること。
- 論文の引用（et al. や年号）、括弧記号は含めないこと。
- 無理に多く抽出せず、本当に重要なものだけを10〜15個程度抽出すること。
- 以下の形式で、1行に1つずつ箇条書きで出力すること。

出力形式:
- 専門用語1
- 専門用語2

テキスト:
{body}"""

def get_translation_prompt(term: str) -> str:
    return f"Translate the following technical term to English. Output ONLY the translated term: {term}"

def get_judgment_prompt(target_page: str, raw_markdown: str) -> str:
    return f"既存のWiki知識と新規情報を比較し、更新が必要か判定せよ。\nターゲット: {target_page}\n新規情報: {raw_markdown}"

def get_refine_prompt(target_page: str, current_content: str, raw_markdown: str, lang_inst: str) -> str:
    return f"""既存のWikiページ [[{target_page}]] を最新情報に基づいて更新・洗練せよ。{lang_inst}
既存の記述を尊重しつつ、新情報を論理的に統合すること。

現状のコンテンツ:
{current_content}

追加・更新すべき新情報:
{raw_markdown}

【言語と表記の指針】
- 専門用語、技術概念（例：Self-RAG, Retrieval, Critique等）については、オリジナルの英語表記を優先してください。

【リンク付与のルール】
- 知識が網の目となるよう、本文中の重要な用語には積極的に `[[用語名]]` の形式で内部リンクを付与してください。
- 英語表記であっても、重要な概念であれば `[[Self-RAG]]` のようにリンクを作成してください。
"""

def get_draft_body_prompt(target_page: str, raw_markdown: str, context: str) -> str:
    return f"""あなたは高度なナレッジエンジニアです。以下の情報を統合し、最高品質のWiki記事を執筆せよ。

ターゲットタイトル: {target_page}
新規情報 (Raw text): {raw_markdown}
コンテキスト (既存知識):
{context}

【執筆の要件】
1. # {target_page} (H1タイトル)
2. > [!abstract] 要約
   記事の核心的な内容、技術的背景、および意義を3行以上で具体的に要約してください。
3. 本文構成:
   - 専門用語（Self-RAG, Retrieval, Critique, LLM等）は英語表記を優先。
   - 重要な用語には積極的に `[[用語名]]` で内部リンクを付与してください。
   - 図、表、箇条書きを活用して、読みやすく構造化してください。

注意: 出力は Markdown 本文のみとし、YAMLフロントマターは含めないでください。
"""

def get_query_prompt(query: str, context: str, lang_inst: str) -> str:
    return f"""あなたはWikiのナレッジアシスタントです。{lang_inst}
以下のWikiページ（整理済み）、関連リンク（自動追跡）、および一次情報（生データ）を参考にして、質問に答えてください。

## コンテキスト
{context}

## 質問: {query}

## 指示:
- {lang_inst}
- Wikiページや関連リンクに概要がある場合はそれを活用し、細かい事実は一次情報から補完してください。
- 根拠となった情報の出典を必ず [[ページ名]] または [[sources/PDF名]] 形式で明記してください。
- 外部の知識は絶対に混ぜないでください。

回答:"""
