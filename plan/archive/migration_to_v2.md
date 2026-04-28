# Architecture v2: Obsidian-Native Workflow Migration [COMPLETED]

## ステータス: 完了 (2024-04-28)
本移行計画はすべて完了し、システムは Obsidian を中心とした手動同期フローに移行しました。

## 完了した項目

### 1. UIおよび監視プロセスの廃止
- **Streamlitダッシュボード (`ui/app.py`) の削除**: 完了。
- **常時監視 (`scheduler.py`) の削除**: 完了。手動トリガー（`main.py --sync`）へ移行。
- **LangGraphの待機状態 (`interrupt`) の削除**: 完了。即時ドラフト生成方式へ。

### 2. インフラストラクチャのデュアル対応
- Qdrant のローカルモード (`path="./qdrant_data"`) 対応完了。`.env` の `QDRANT_MODE` で切り替え可能。

### 3. レビュー手法の変更 (`#未審査` タグ方式)
- **`_staged/` ディレクトリの廃止**: 完了。`wiki/` 直下に直接出力。
- **タグによる保護**: フロントマターに `tags: [未審査]` を自動付与。
- **同期ロジックの変更**: `retrieval/sync_manager.py` および `retrieval/qdrant_store.py` において、`未審査` タグが含まれるファイルを無視するロジックの実装完了。

## 実行フェーズのステップ
1. **設定・コア部分の改修**: `.env.example` の更新と、`qdrant_store.py` のローカルモード対応。
2. **出力・同期ロジックの改修**: `obsidian_writer.py` を `_staged` 経由から直書きへ変更し、`sync_manager.py` にタグ除外フィルターを追加。
3. **ワークフローの簡略化**: `graph.py` から `interrupt` を削除し、`main.py` の手動同期コマンドの整理。
4. **不要ファイルの削除**: `scheduler.py`、`ui/app.py` などをクリーンアップ。
5. **ドキュメントの更新**: `AGENTS.md`、`README.md`、`docs/USER_GUIDE.md` を新方式に合わせて書き換える。
