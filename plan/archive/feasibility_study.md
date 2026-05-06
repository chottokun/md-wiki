# 実装可能性検討レポート (Feasibility Study)

本プロジェクト（12GB VRAM環境下でのハイブリッドRAG-Wiki・HITLアーキテクチャ）の理論的な実現可能性について、最新の技術動向とAPI仕様に基づく調査結果をまとめる。

## 1. RTX 3060 12GBでの「逐次入れ替え」の実現性
**結論: 実現可能（非常に現実的）**

- **VRAM使用量の見積もり**:
  - Qwen 2.5 7B / Llama 3 8B (Q4量子化): 約5.5GB〜6.5GB
  - VLM (Gemma 2 2B / Qwen2-VL 2B): 約2GB〜3GB
  - 埋め込みモデル (mxbai-embed-large): 約1GB未満
  - *同時ロードはVRAMオーバーフローのリスクがあるが、単独であれば12GB内に十分に収まる。*
- **Ollamaによるメモリ管理**:
  - OllamaのAPI呼び出し時に `keep_alive: 0` というパラメータを付与することで、生成完了後に**即座にVRAMからモデルをアンロード**できることが確認された。
  - これにより、インジェスト時（VLM）と推論時（7B LLM）の「逐次入れ替え」をコードレベルで完全に自動化し、VRAM枯渇を防ぐことが可能。

## 2. LangGraphによるHITL (Human-in-the-Loop) の実現性
**結論: 実現可能（最新APIでネイティブサポート）**

- **`interrupt()` と `Command(resume=...)`**:
  - LangGraphの最新仕様では、ノード内で `interrupt()` 関数を呼び出すことで、実行状態をチェックポインター（`MemorySaver` 等）に保存したまま完全にグラフを一時停止できる。
  - Obsidian上で人間が差分を確認・修正した後、外部スクリプトから `graph.invoke(Command(resume="approve"), config)` を発行するだけで、中断したノードから正確に処理を再開できる。これは本計画の「レビュー承認フロー」と完璧に合致する。

## 3. Qdrantによるハイブリッド検索
**結論: 実現可能**

- Qdrant自体はDockerコンテナとしてホストの通常RAMを使用するため、VRAMを圧迫しない。
- Dense（ベクトル）とSparse（BM25キーワード）のインデックス作成、およびRRF（Reciprocal Rank Fusion）による統合検索はQdrantの標準機能として提供されており、LangChain経由で容易に実装可能。

---
以上の調査から、本計画は技術的なボトルネックが存在せず、極めて妥当で実現性の高いアーキテクチャであると断言できる。

## 4. 関連技術リファレンス（公式ドキュメント等）
実装時に参照すべき重要技術の一次情報（リファレンス）を以下にまとめる。

- **Ollama のVRAM管理 (`keep_alive`)**
  - [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md): `keep_alive` パラメータの仕様。デフォルトは5分だが、`0` に設定することでリクエスト完了直後に即座にVRAMを解放できる公式仕様。
  - [Ollama FAQ: How do I keep a model loaded in memory or make it unload immediately?](https://github.com/ollama/ollama/blob/main/docs/faq.md#how-do-i-keep-a-model-loaded-in-memory-or-make-it-unload-immediately)

- **LangGraph のHuman-in-the-Loop (HITL)**
  - [LangGraph How-to Guides: Human-in-the-loop](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/): 処理の一時停止 (`interrupt()`) と、外部からの処理再開 (`Command(resume=...)`) の設計パターン解説。
  - [LangGraph Concepts: Persistence](https://langchain-ai.github.io/langgraph/concepts/persistence/): `MemorySaver` 等を用いて、一時停止中もエージェントのステータス（履歴や状態）を永続化・保持する仕組み。

- **Qdrant のハイブリッド検索**
  - [Qdrant Articles: Hybrid Search](https://qdrant.tech/articles/hybrid-search/): Dense（意味）ベクトルとSparse（キーワード）ベクトルを組み合わせ、RRF (Reciprocal Rank Fusion) によって精度を高める実装手法。
