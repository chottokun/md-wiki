# 開発環境セットアップ方針 (Setup Guide)

本プロジェクトの実装を開始するための、基盤セットアップ手順と方針を定義する。

## 1. パッケージ管理とPython環境 (uv)
`uv` を用いて、軽量かつ高速な依存関係管理と仮想環境構築を行う。

- **プロジェクト初期化**: 
  - `uv init` にてプロジェクトの雛形 (`pyproject.toml`, `hello.py` 等) を作成する。
- **主要依存パッケージの追加**:
  - LLM基盤: `langchain`, `langchain-community`, `langgraph`
  - インジェスト: `docling`
  - ベクターストア: `qdrant-client`
  - 型定義・設定: `pydantic`, `python-dotenv`

## 2. インフラ環境構築 (Docker Compose)
ローカルの依存サービス（Ollama、Qdrant）をカプセル化し、一貫した実行環境を提供する。

- **`docker-compose.yml` の構成**:
  - `ollama`: ホストのGPU (`deploy: resources: reservations: devices`) をマウントしたOllamaサーバー。
  - `qdrant`: 永続化ボリューム (`./data/qdrant:/qdrant/storage`) をマウントしたベクトルデータベース。

## 3. ディレクトリ・アーキテクチャの構築
`plan/rag-wiki.md` および `plan/modules.md` で定義した構造を物理的に作成する。

```text
RAG-wiki/
├── _raw/             # ユーザーがPDF等を投入するインプットフォルダ
├── _staged/          # Markdown変換結果や差分（レビュー待ち）が出力される一時フォルダ
├── wiki/             # 承認済みのMarkdownが保存されるObsidianボルトルート
├── core/             # モジュール1: LLMルーター
├── ingestion/        # モジュール2: Doclingパーサー
├── retrieval/        # モジュール3: Qdrantストア
├── output/           # モジュール4: Obsidian差分・ファイル出力
├── agent/            # モジュール5: LangGraph定義
├── docker-compose.yml
├── pyproject.toml
└── .env              # LLM_PROVIDER=ollama 等の環境変数
```

このセットアップ方針に沿って、基盤構築（Step 0）を進める。
