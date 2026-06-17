# md-wiki (自律成長型 Wiki-Native RAG システム)

ローカルLLM（Ollama/Gemma 4）と Obsidian を高度に統合し、投入された一次情報から永続的かつ構造化されたナレッジベース（Wiki）を半自動的に構築・維持する、自律成長型のナレッジ管理・RAG（Retrieval-Augmented Generation）システム。

## 🌟 コア・コンセプト

1. **Knowledge Compiling (知識のコンパイル)**
   一次情報から抽出されたナレッジを、重複のない永続的なWikiページ群へと統合する。原子性（1ページ＝1概念）を重視し、関連用語を自動的に相互参照（`[[ページ名]]` による Cross-linking）する。
2. **Raw + Compiled Hybrid RAG (ハイブリッド・インデックス設計)**
   Qdrant ベクトルデータベース内に、一次情報（Raw Source）の「不変の事実」と、AIおよび人間によって編集・構造化されたWiki（Compiled Wiki）の「流動的な知見」を共存させ、高精度なコンテキスト検索（Dense + Sparse ハイブリッド検索）を実現する。
3. **Obsidian-Native HITL (Human-in-the-Loop)**
   AIは生成したドラフトを `wiki/` へ直接出力し、自動的に `tags: [未審査]` をフロントマターに付与する。人間は Obsidian などのマークダウンエディタ上で差分を確認・承認（`未審査` タグの削除）し、明示的に同期コマンドを実行することでインデックスへ反映させる。
4. **OKF v0.1 Conformance (Open Knowledge Format 準拠)**
   YAML Frontmatter の構造を OKF v0.1 規格に準拠し、Pydantic スキーマ (`WikiFrontmatterSchema`) で厳格に定義・強制する。`type` フィールドによる分類（Concept, Article, Source, RawSource 等）を行い、`timestamp` の ISO 8601 化、`index.md` によるディレクトリ解説、および `log.md` 履歴の OKF 日付グループ化をサポート。
5. **Decoupled Repository Design (分離型リポジトリ設計)**
   システム本体のソースコード（メイン）と、ナレッジベース（`wiki/`）の Git リポジトリ履歴を完全に分離し、知識資産のポータビリティと独立したライフサイクルを確保する。

---

## 🚀 セットアップ

本システムは、コンテナインフラを必要としない「Local Mode」（デフォルト）と、Dockerを利用した「Server Mode」の双方に対応している。

### 1. 依存パッケージのインストール
`uv` を利用して仮想環境およびパッケージの同期を行う。
```bash
uv sync
```

### 2. 環境変数の設定 (`.env`)
`.env.example` を参考に、ルートディレクトリに `.env` ファイルを作成する。

```env
# Qdrantの動作モード (local: ./qdrant_data に永続化, server: 外部サーバー利用)
QDRANT_MODE=local
QDRANT_URL=http://localhost:6333

# 埋め込みモデル (Ollama)
EMBEDDING_MODEL=mxbai-embed-large
LOCALLLM_BASE_URL=http://localhost:11434

# LLMプロバイダー設定 (ollama, openai_compatible, gemini)
LLM_PROVIDER=ollama
TARGET_LANGUAGE=Japanese

# L1/L2タスク向けローカルLLM設定 (Ollama)
LOCALLLM_MODEL=gemma4:latest
STANDARDLLM_MODEL=gemma4:latest

# L3タスク（高度な推論・競合解決）向け OpenAI互換API（さくらAI Engine等）
OPENAI_COMPATIBLE_MODEL=gpt-oss-120b
OPENAI_COMPATIBLE_API=your_api_key_here
OPENAI_COMPATIBLE_BASE_URL=https://api.example.com/v1

# 日本語エンコーディングの統一設定（Windows環境推奨）
PYTHONUTF8=1
PYTHONIOENCODING=utf-8
```

---

## 🛠️ CLI 運用マニュアル

統合 CLI ツールである `main.py` を通して、ナレッジのインジェスト、検索、同期、自動診断を実行する。

### 1. 知識のインジェスト (Ingestion)
一次資料（PDF等）をシステムに読み込ませ、Wikiドラフトを自動生成する。
```bash
uv run python main.py _raw/example.pdf
```
- **処理内容**: PDFを高精度にパースし、既存Wikiとのマージ比較を行いながら、新規または追記のドラフトを `wiki/` 直下に生成する。新規生成ページには自動的に `#未審査` タグが付与される。
- `--yes` (`-y`) オプションを付与することで、人間による確認プロンプトをスキップして自動的に承認・書き込みを完了できる。

### 2. レビューと承認 (Review & Approve)
1. Obsidian（または任意のMarkdownエディタ）で `wiki/` を開き、生成されたドラフトを確認する。
2. 内容が妥当であれば、YAMLプロパティの `tags` から `未審査` を削除（または変更）する。
3. 手動で追記した `## 💡 人間の考察` セクションは、将来の自動更新時にもAIによって削除されず、そのまま引き継がれる。

### 3. ベクトルインデックスへの同期 (Synchronization)
審査済み（`未審査` タグが外された）のWikiファイルをベクトルデータベース（Qdrant）に反映し、Gitコミットを記録する。
```bash
uv run python main.py --sync
```
- 短縮形: `uv run python main.py -s`
- `--force` (`-f`) オプションを使用すると、未審査のページを含めて強制的に同期を実行する。

### 4. ハイブリッド検索と質問回答 (Query & RAG Search)
蓄積された構造化Wikiと一次資料を横断的に検索し、コンテキスト情報を動的抽出した高精度な回答を生成する。
```bash
uv run python main.py --query "RAGにおけるハイブリッド検索の優位性とは？"
```
- 短縮形: `uv run python main.py -q "質問内容"`

### 5. 自動整合性チェックと健康診断 (Linting)
Wiki内のリンク切れや、言及されているが存在しない空リンク（Red Links）を検出し、AIによる自動起票・修復（スタブページの作成）を実行する。
```bash
uv run python main.py --lint
```
- 短縮形: `uv run python main.py -l`
- `--dry-run` を付与することで、実際の書き込みを行わずに警告や検知内容のみをログに出力できる。

### 6. 手動編集ページの洗練と競合解決 (Refine & Conflict Resolution)
手動で加筆したWikiページをAIでさらに洗練させ、またはGitのマージ競合（衝突マーカー）を自動解決する。
```bash
uv run python main.py --refine "ページ名"
```
- 短縮形: `uv run python main.py -r "ページ名"`
- **コンフリクト自動解決**: ファイル内に Git 衝突マーカー (`<<<<<<<`, `=======`, `>>>>>>>`) が含まれている場合、自動的に競合解決モードが起動し、文脈と一次ソースの整合性を保ちながらピンポイントで修復を行う。

### 7. 特定トピックの統合要約レポート作成 (Landscape Synthesis)
特定トピックに関する分散された知識を集約し、俯瞰的なランドスケープレポートを生成する。
```bash
uv run python main.py --maintenance "トピック名"
```
- 短縮形: `uv run python main.py -m "トピック名"`

---

## 🧹 ユーティリティ・スクリプト

### 全Wiki・インデックスのクリーン・リビルド
`_raw/` 内の一次情報（PDF）からすべてのWikiページを完全再構成する。
```bash
uv run python auto_rebuild.py
```
- **処理フロー**: 
  1. Qdrantコレクションを完全削除。
  2. `wiki/` 内の Markdown ファイルをリセット（`Home.md`, `log.md`, `sources/` は保護）。
  3. `_raw/` 内の全PDFを自動承認モードで順次インジェストし、強制同期。
  4. `--lint` を実行して Red-link の自動修復とインデックス接続を完了。

### システム環境の完全初期化 (Hard Reset)
全Wikiページ、ログ、Qdrantデータディレクトリを一括削除し、完全にクリーンな初期状態に戻す。
```bash
uv run python reset_vault.py
```

### OKF マイグレーションと適合性チェック

既存の Wiki を OKF 形式に移行し、適合性を検証するためのツール群。

**1. 一括マイグレーションスクリプト**
```bash
# 既存の wiki/ ディレクトリを OKF v0.1 形式へマイグレーション（バックアップ作成付き）
uv run python migrate_to_okf.py --backup
```

**2. OKF 適合性チェック (Linter)**
```bash
# wiki/ ディレクトリの OKF v0.1 適合性チェックを実行
uv run python okf_lint.py wiki/
```

---

## 📁 ディレクトリ構造

```
md-wiki/
├── wiki/                   # OKF Knowledge Bundle (Obsidian Vault)。独立したGitリポジトリ。
│   ├── index.md            # OKF §6 ディレクトリインデックス（フロントマターなし）
│   ├── log.md              # OKF §7 日付グループ化された更新履歴ログ
│   ├── concepts/           # 技術用語解説（type: Concept）
│   │   └── index.md        # 自動生成された用語インデックス
│   ├── sources/            # 根拠となるオリジナルPDF等の保管庫
│   └── raw_markdown/       # type: RawSource frontmatter が付与された解析済中間テキスト
├── _raw/                   # インジェスト前の生データ（PDF/MD）配置ディレクトリ
├── migrate_to_okf.py       # OKF 移行用バッチマイグレーションツール
├── okf_lint.py             # OKF v0.1 適合性チェッカー (Linter)
├── agent/                  # LangGraph による自律成長型エージェントワークフローの定義
├── core/                   # メタデータ(Pydantic)スキーマ、環境設定、LLMルーティングロジック
├── retrieval/              # ハイブリッド検索エンジン、GitおよびDB同期マネージャー
├── output/                 # Obsidianライター、変更履歴・動作ログ管理
├── docs/                   # アーキテクチャ解説、設計思想、詳細ユーザーガイド
├── plan/                   # ロードマップ、履歴、Wikiフォーマット規約（WIKI_FORMAT.md）
├── tests/                  # 単体・結合テストコード（pytest）
├── pyproject.toml          # プロジェクト依存関係とパッケージ構成 (uv対応)
└── README.md               # 本ドキュメント（本ファイル）
```

---

## 🛠️ 技術スタック
- **LLM Routing**: [Sakura AI / OpenAI Compatible](https://example.com) (L3: 高度な推論・競合解決) / [Ollama](https://ollama.com) (L1/L2: 軽量・標準タスク)
- **Workflow Engine**: [LangGraph](https://www.langchain.com/langgraph) (Agentic State Machine & Review Points)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/) (Strict Metadata Governance)
- **Vector DB**: [Qdrant](https://qdrant.tech/) (Dense + Sparse Hybrid Search with Local Persistence)
- **PDF Parser**: [Docling v2](https://github.com/DS4SD/docling) (High-fidelity Document Layout Analysis)
- **Knowledge IDE**: [Obsidian](https://obsidian.md/) (Local-first Markdown Vault)
