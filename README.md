# md-wiki: 知能的協調型ナレッジベース

RAG-Wiki は、ローカルLLM (Ollama/Gemma 4) と Obsidian を組み合わせた、自律成長型のナレッジ管理システムです。
単なる情報検索 (RAG) を超え、投入された知識を既存の Wiki とマージし、知的なネットワークを構築します。

## 🌟 コア・コンセプト
- **Knowledge Compiling**: 情報を使い捨てにせず、永続的なWikiページへと「コンパイル（集約・統合）」します。
- **Raw + Compiled Hybrid RAG**: 原始資料 (Raw) の事実と、AIが整理した知見 (Wiki) の両方を検索対象とし、極めて高い推論精度を実現します。
- **Human-in-the-Loop (HITL)**: AIは勝手にWikiを書き換えません。人間が Obsidian で差分を確認し、承認した内容のみが反映されます。
- **Scalable Maintenance**: Git 履歴に基づく健康診断 (Linting) や、トピックごとの自動要約 (Synthesis) により、数千ページ規模への拡大に対応します。

## 🚀 クイックスタート

### 1. 環境構築
```bash
# 依存関係のインストール
uv sync
# インフラ（Ollama, Qdrant）の起動
docker compose up -d
```

### 2. 知識の投入 (Ingest)
PDFやメモを `_raw/` に入れ、以下のコマンドを実行します。
```bash
uv run python main.py _raw/paper.pdf
```
- `-y` フラグを付けると、AIの提案を自動承認して高速にインポートします。

### 3. 知識の活用 (Query)
Wikiの内容に基づいた質問が可能です。
```bash
uv run python main.py --query "Self-RAGのReflectionトークンについて教えて"
```

### 4. メンテナンス (Synthesis / Lint)
```bash
# 特定トピックの統合レポート作成
uv run python main.py -m "RAG手法の比較"
# Wikiの整合性チェック（リンク切れ、風化）
uv run python main.py --lint
```

## 🛠️ 技術スタック
- **LLM**: Gemma 4 (Local), Sakura AI Engine (Cloud)
- **Framework**: LangChain, LangGraph
- **Vector DB**: Qdrant (Hybrid Search: Dense + Sparse)
- **Parser**: Docling v2 (High-fidelity PDF-to-Markdown)
- **UI**: Obsidian (The IDE for Knowledge)

## 📁 ディレクトリ構造
- `wiki/`: 完成したWiki（Obsidian Vault）。Gitで独立管理。
- `wiki/sources/`: 根拠となるオリジナルPDF。
- `_raw/`: 投入前の生データ。
- `agent/`: LangGraph によるエージェントロジック。
- `docs/`: 詳細な設計・運用マニュアル。
