# プロジェクト進捗・状態記録 (TODO & Status)

本ドキュメントは、開発中のクラッシュやセッション中断に備え、常に現在の完了ステータスと次に行うべきアクションを記録するためのものです。エージェントはアクション完了ごとにこのファイルを更新してください。終わったものはステータスを[x]に書き換えてください。過去の経歴は、HISTORY.mdに移動し、現在のステータスをリセットしてください。

## 📍 現在のステータス (Current Status)
- [x] プロジェクト方針の策定 (`plan/rag-wiki.md` の作成)
- [x] モジュール分割計画の策定 (`plan/modules.md` の作成)
- [x] 環境構築方針の策定 (`plan/setup_guide.md` の作成)
- [x] 実装可能性の調査・リファレンスまとめ (`plan/feasibility_study.md` の作成)
- [x] エージェントの行動指針の策定 (`AGENTS.md` の作成とTDDルールの追記)
- [x] LLM環境設定の確認 (`.env` にさくらのAI EngineとOllamaの設定完了)
- [x] プロジェクトの初期化 (`uv init` およびディレクトリ構造の作成)
- [x] インフラ環境の構築 (`docker-compose.yml` の作成)
- [ ] モジュール1: LLMルーターの実装 (`core/llm_router.py`)

## 🚀 次のアクション (Next Action)
1. **モジュール1: LLMルーターの実装**:
   - `core/llm_router.py` を作成し、Layer 1〜3のモデル切り替えロジックを実装する。
   - `tests/test_llm_router.py` を作成し、単体テストを行う。

## 📝 メモ・懸案事項 (Notes)
- `.env` に設定された `OPENAI_COMPATIBLE_MODEL=gpt-oss-120b` (さくらのAI Engine) はLayer 3の推論で使用する。
- ローカルLLMは `LOCALLLM_MODEL=ollama/gemma4:latest` と設定されているが、実際のモデル名に合わせて適宜調整すること。
- TDD（テスト駆動開発）を原則とし、各モジュールはLangGraphに組み込む前に単独テストを通過させること。
