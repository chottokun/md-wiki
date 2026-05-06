# プロジェクト進捗・状態記録 (TODO & Status)

本ドキュメントは、開発中のクラッシュやセッション中断に備え、常に現在の完了ステータスと次に行うべきアクションを記録するためのものです。エージェントはアクション完了ごとにこのファイルを更新してください。終わったものはステータスを[x]に書き換えてください。過去の経歴は、HISTORY.mdに移動し、現在のステータスをリセットしてください。

## 📍 現在のステータス (Current Status)
- [x] ハイブリッドRAGアーキテクチャの確立 (Raw + Compiled Wiki)
- [x] 120BクラスLLM (Sakura API) による高品質ナレッジコンパイル
- [x] Obsidian を IDE とする HITL ワークフローの完成
- [x] 履歴と知識の分離管理 (wiki/ ディレクトリの独立)
- [x] 統合 CLI ツール (main.py) の多機能化 (Ingest, Query, Sync, Lint)
- [x] **Architecture v2: Obsidian-Native Workflow への移行完了**
    - [x] Docker依存の排除 (Qdrant ローカルモード対応)
    - [x] `_staged` の廃止と `wiki/` への直接ドラフト出力 (`tags: [未審査]` 方式)
    - [x] 明示的同期 (`main.py --sync`) への移行と監視スクリプトの廃止
    - [x] 不要なUI (Streamlit) への依存削除
    - [x] **知識パイプラインの安定化と品質向上 (2026-04-28)**
        - [x] Pydantic によるメタデータ (Frontmatter) の厳格管理の実装
        - [x] 「自動生成スタブ」を禁止する要約品質バリデータの導入
        - [x] 用語抽出 (lint) 時のエイリアス定義の厳格化
        - [x] 全Wikiデータのクリーン・リビルドの完遂
    - [x] **コードのクリーンアップとTDDベースの再整備**
        - [x] `_staged` 関連のコードを完全に削除
        - [x] `agent/graph.py` の冗長な `retrieve_node` を統合・簡略化
        - [x] `QdrantHybridStore` および `ObsidianWriter` のテストを最新仕様に更新

## 🚀 次のアクション (Future Roadmap)

### v1.2: インテリジェンスの深化と品質向上
- [ ] **監査用LLM (Audit Node) の本格導入**:
    - Tier 1/2 の軽微な更新を Layer 3 LLM が自動評価し、人間のレビュー負荷をさらに軽減。
- [ ] **検索精度の向上**:
    - ハイブリッド検索の重み付け調整 (Dense vs Sparse) の最適化。
    - リンクグラフを活用した再帰的なコンテキスト拡張の洗練。
- [ ] **ドキュメントの完全整備**:
    - `USER_GUIDE.md` を v2 の「手動同期・タグ審査」フローに合わせて全面的にリライト。
    - `README.md` のセットアップ手順を最新化。

### 長期的課題
- [ ] マルチモーダル対応 (画像の埋め込みとWiki統合)。
- [ ] 外部ツール (ブラウジング等) との連携による最新情報の補完。


## 📝 メモ・懸案事項 (Notes)
- `.env` に設定された `OPENAI_COMPATIBLE_MODEL=gpt-oss-120b` (さくらのAI Engine) はLayer 3の推論で使用する。
- ローカルLLMは `LOCALLLM_MODEL=ollama/gemma4:latest` と設定されているが、実際のモデル名に合わせて適宜調整すること。
- TDD（テスト駆動開発）を原則とし、各モジュールはLangGraphに組み込む前に単独テストを通過させること。
