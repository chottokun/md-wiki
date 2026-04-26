# プロジェクト進捗・状態記録 (TODO & Status)

本ドキュメントは、開発中のクラッシュやセッション中断に備え、常に現在の完了ステータスと次に行うべきアクションを記録するためのものです。エージェントはアクション完了ごとにこのファイルを更新してください。終わったものはステータスを[x]に書き換えてください。過去の経歴は、HISTORY.mdに移動し、現在のステータスをリセットしてください。

## 📍 現在のステータス (Current Status)
- [x] ハイブリッドRAGアーキテクチャの確立 (Raw + Compiled Wiki)
- [x] 120BクラスLLM (Sakura API) による高品質ナレッジコンパイル
- [x] Obsidian を IDE とする HITL ワークフローの完成
- [x] 履歴と知識の分離管理 (wiki/ ディレクトリの独立)
- [x] 統合 CLI ツール (main.py) の多機能化 (Ingest, Query, Sync, Lint)
- [x] 堅牢なテストスイート (TDD) の整備

## 🚀 次のアクション (Future Roadmap: v1.1)
1. **Git駆動の差分同期 (Incremental Sync)**:
   - 全件再構築を回避し、`git diff` を活用して変更されたファイルのみを Qdrant に反映する。
   - 同期済みのコミットハッシュを管理する仕組みの導入。
2. **監査用LLM (Audit Node) の導入**:
   - Tier 1/2 の軽微な更新を Layer 3 LLM が自動評価し、人間のレビュー負荷をさらに軽減する。
3. **視覚的整合性の向上**:
   - Broken Link (Red-links) を AI が自動で解決（新規ページの下書き作成）する機能。

## 📝 メモ・懸案事項 (Notes)
- `.env` に設定された `OPENAI_COMPATIBLE_MODEL=gpt-oss-120b` (さくらのAI Engine) はLayer 3の推論で使用する。
- ローカルLLMは `LOCALLLM_MODEL=ollama/gemma4:latest` と設定されているが、実際のモデル名に合わせて適宜調整すること。
- TDD（テスト駆動開発）を原則とし、各モジュールはLangGraphに組み込む前に単独テストを通過させること。
