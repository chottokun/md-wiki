# RAG-Wiki ユーザーガイド

本システムは、ローカルLLMを活用して、投入されたドキュメントから自動的にナレッジベース（Wiki）を構築・管理するためのツールです。

## 🛠️ 基本的な操作

### 1. 知識の投入 (Ingestion)
PDF、Markdown、テキストファイルなどの生データをWikiに取り込みます。
```bash
uv run python main.py _raw/example.pdf
```
- **プロセス**: 文書解析 -> 関連知識の検索 -> Wiki執筆案作成 -> レビュー待ち

### 2. レビューと承認 (HITL)
AIが作成したマージ案を `_staged/` ディレクトリで確認します。
- CLI上で `a` (approve) を押すと、Wikiに正式に反映されます。
- `r` (reject) を押すと、その提案は破棄されます。

### 3. 知識の検索と活用 (Query)
...（中略）...

### 4. ナレッジ・メンテナンス (Synthesis)
蓄積された複数のページを横断的に要約し、トピックごとの全体像（Landscape Report）を作成します。週に一度の「知の整理」に最適です。
```bash
uv run python main.py -m "RAG手法の進化" --yes
```
- **効果**: 散らばった知識が統合され、手法間の比較や矛盾の発見が自動で行われます。
- **ログ**: メンテナンス活動は `wiki/log.md` に時系列で記録されます。

### 5. システムの完全再構築 (Rebuild from Scratch)
モデルの変更（例: OllamaからSakura APIへの切り替え）や、プロンプトの抜本的な見直しを行った場合、蓄積された全データを一から再構築（コンパイル）することができます。

```bash
# 1. Qdrant データベースと既存のWikiファイルのリセット
# (wiki/sources のPDFや、wiki/.git の履歴は保護されます)
uv run python -c "from retrieval.qdrant_store import QdrantHybridStore; QdrantHybridStore().client.delete_collection('rag_wiki')"
find wiki/ -name "*.md" ! -name "Home.md" ! -name "log.md" -delete
rm -f _staged/*.md

# 2. 自動再構築スクリプトの実行
# _raw/ 内のすべてのPDFを自動承認モード (-y) で一括再インジェストします
uv run python auto_rebuild.py
```

## ⚙️ 詳細設定 (.env)
システムの振る舞いは `.env` ファイルで制御できます。
- `LLM_PROVIDER`: `ollama` (ローカル) または `openai_compatible` (さくらAPI等クラウド) を選択。
- `TARGET_LANGUAGE`: `Japanese` 等を指定すると、全プロンプトの出力言語が強制されます。
- `CHUNK_SIZE` / `CHUNK_OVERLAP`: Qdrantに保存する際のテキスト分割サイズ（長文PDFの検索精度に直結します。デフォルトは400/50）。
...

- `_raw/`: 解析前の生データを置く場所
- `_staged/`: AIが作成したレビュー待ちの差分ファイル
- `wiki/`: 承認済みのWiki（Obsidian Vault）
- `docs/`: 本ドキュメント類

## 🎨 閲覧と編集のベストプラクティス

### 1. 閲覧のコツ (Obsidian)
- **グラフビュー**: `Ctrl+G` で知識のネットワークを俯瞰できます。
- **アウトライン**: 右サイドバーの「Outline」を有効にすると、AIが構造化した見出しを一覧でき、長い論文も素早く把握できます。

### 2. 人間による追記
AIと協力してWikiを育てるために、以下のセクションを自由に活用してください。AIはこれらのセクションを自動的に保護し、新しい情報を取り込む際も維持し続けます。
- `## 💡 人間の考察`: あなたが論文を読んで感じたこと、独自の洞察。
- `## 📝 メモ`: 自分向けの備忘録、関連するプロジェクトのリンク。

### 3. 編集の流儀
- **プロパティの編集**: ページ上部のプロパティからタグやステータスを編集すると、AIが次回の更新時にそのスタイルを学習します。
- **リンクの作成**: 新しい用語を見つけたら `[[ ]]` で囲んでください。AIがそれを「ナレッジの予約」として認識し、次回以降のインジェスト時にその用語の詳細を埋めようとします。
