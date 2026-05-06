# Wiki型ナレッジベース

ローカルLLM (Ollama/Gemma 4) と Obsidian を組み合わせた、自律成長型のナレッジ管理システムを考えています。投入された知識を既存の Wiki とマージし、知的なネットワークを構築します。そのwikiをRAGとして利用します。

## 🌟 コア・コンセプト
- **Knowledge Compiling**: 情報を使い捨てにせず、永続的なWikiページへと「コンパイル（集約・統合）」します。
- **Raw + Compiled Hybrid RAG**: 一次情報 (Raw) の事実と、AIが整理した知見 (Wiki) の両方を検索対象とし、極めて高い推論精度を実現します。
- **Human-in-the-Loop (HITL)**: AIは勝手にWikiを書き換えません。人間が Obsidian で差分を確認し、承認した内容のみが反映されます。
- **Scalable Maintenance**: Git 履歴に基づく健康診断 (Linting) や、トピックごとの自動要約 (Synthesis) により、数千ページ規模への拡大に対応します。
## 🚀 クイックスタート

本システムは、コンテナを使わない「Local Mode」と、Docker/Podmanを利用する「Server Mode」のデュアル環境に対応しています。

### 1. 環境設定 (`.env`)
`.env` ファイルを作成し、Qdrantの動作モードを指定します。
```env
# Local Mode (コンテナ不要、ディレクトリ保存)
QDRANT_MODE=local

# Server Mode (Docker/Podman利用時)
# QDRANT_MODE=server
# QDRANT_URL=http://localhost:6333
```

### 2. 環境構築と起動
```bash
# 依存関係のインストール
uv sync

# [Server Modeの場合のみ] インフラの起動
# docker compose up -d
```
※ Ollamaは、いずれのモードでもホストOSで直接実行するか、お好みの方法で起動してください（デフォルトポート `11434`）。

### 3. インジェストとレビュー
1. **知識の投入**: 一次情報（PDF等）を読み込ませます。
   ```bash
   uv run python main.py _raw/example.pdf
   ```
2. **レビュー**: Obsidianを開き、`wiki/` 内に生成されたページ（`tags: [未審査]` が付与されています）を確認・編集します。
3. **承認と同期**: Obsidian上で `#未審査` タグを削除し、以下のコマンドでデータベースへ反映させます。
   ```bash
   uv run python main.py --sync
   ```

### 4. 検索とメンテナンス
```bash
# Wikiの整合性チェックと未作成ページの自動執筆 (Linting)
uv run python main.py --lint

# 全WikiページとDBのクリーン・リビルド
# (_raw/ 内のPDFから全てのWikiページを再構成します)
uv run python auto_rebuild.py

# 特定トピックの統合レポート作成
uv run python main.py -m "RAG手法の比較"
```

### ユーティリティ
- **環境のリセット**: 全Wikiページ、ログ、Qdrantデータを一括削除してクリーンな状態に戻します。
  ```bash
  python reset_vault.py
  ```

## 🛠️ 技術スタック
- **LLM**: Ollama (Local), Sakura AI (Cloud)
- **Framework**: LangGraph (Agentic Workflow)
- **Schema**: Pydantic v2 (Strict Metadata Governance)
- **Vector DB**: Qdrant (Hybrid Search: Dense + Sparse)
- **Parser**: Docling v2 (High-fidelity PDF-to-Markdown)
- **UI**: Obsidian (The IDE for Knowledge)

## 📁 ディレクトリ構造
- `wiki/`: 完成したWiki（Obsidian Vault）。Gitで独立管理。
- `wiki/sources/`: 根拠となるオリジナルPDF。
- `_raw/`: 投入前の生データ。
- `agent/`: LangGraph によるエージェントロジック。
- `docs/`: 詳細な設計・運用マニュアル。
