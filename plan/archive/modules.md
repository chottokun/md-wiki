# 開発モジュール分割計画

本プロジェクトは、テスト可能性と保守性を高めるため、以下の5つの独立モジュールに分割して開発・テストを行い、最後にLangGraphで統合する。

## 1. 基盤モジュール：LLMルーター＆プロバイダー抽象化 (`core/llm_router.py`)
- **役割**: `.env` で定義された環境変数 (`LOCALLLM_MODEL`, `OPENAI_COMPATIBLE_MODEL` 等) を読み込み、タスク難易度（Layer 1〜2のローカル、Layer 3のさくらのAI Engine）に応じたモデルルーティングを行う。
- **テスト**: LLMの設定を切り替え、ローカルOllamaとリモートのさくらのAI Engine (`gpt-oss-120b`) からそれぞれ返答が得られるか単独で確認。

## 2. 入力モジュール：Docling Markdown変換 (`ingestion/docling_parser.py`)
- **役割**: `_raw/`内のPDF/画像を読み込み、Doclingを用いてクリーンなMarkdownに変換して `_staged/` に保存。
- **テスト**: LLM推論を介さず、サンプルPDFが正しくMarkdown化されるか確認。

## 3. 検索モジュール：Qdrantハイブリッド検索 (`retrieval/qdrant_store.py`)
- **役割**: Markdownをチャンク化してQdrantに保存し、Dense+Sparseのハイブリッド検索（RRF）を実行。
- **テスト**: ダミーテキストを保存し、クエリに対して正しくTop N件が検索されるか確認。

## 4. 出力・HITLモジュール：Obsidian差分生成 (`output/obsidian_writer.py`)
- **役割**: 既存WikiとLLM提案内容の差分（Diff）を作成し、Obsidian上でレビュー可能なフォーマットで出力。
- **テスト**: 元テキストと更新案を入力し、期待通りの差分ファイルが生成されるか確認。

## 5. 結合モジュール：LangGraphワークフロー (`agent/graph.py`)
- **役割**: モジュール1〜4を統合し、`interrupt()`を用いた人間介在（HITL）のエージェントループを定義。
- **テスト**: 各コンポーネントをモックし、状態遷移と承認待ち状態での停止を確実に確認。
