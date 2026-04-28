# Wiki Knowledge Pipeline Stabilization & Concept Link Restoration Plan

## 課題の背景とデグレの要因
1. **用語リンクの抜け漏れ**: `draft_node` を自由形式テキスト生成 (2-step) に移行した際、LLM がプロンプトの指示に従わず `[[用語]]` リンクの付与をサボる（省略する）傾向が強まりました。これが原因で、Red-link（未作成リンク）が減少し、結果として `lint_node` が作動しなくなっています。
2. **概念ページの未生成 (`wiki/concepts/`)**: リンクが少ないことに加え、`lint_node` が「Qdrant に明確なエビデンスがある場合のみ」概念ページを作成する厳格な条件になっているため、少しでも検索スコアが低いと生成がスキップされてしまっています。

## 解決策の提案

### 1. 自動リンク付与の確実化 (Post-processing)
LLM の出力に依存せず、プログラム的に確実にリンクを付与する後処理を実装します。
- `draft_node` の Step 2 で抽出された `concepts`（主要概念）のリストを活用します。
- 生成された `body`（本文）をスキャンし、`concepts` に含まれる用語がプレーンテキストとして存在していれば、正規表現を用いて自動的に `[[用語]]` で囲む（Auto-linking）処理を追加します。
- これにより、LLM がリンクをサボっても、重要な用語は 100% リンク化されます。

### 2. 概念ページ生成 (Linting) の条件緩和
- `lint_node` において、Red-link が見つかった際、Qdrant 検索の結果が不十分であっても「スタブ（仮のページ）」として概念ページを生成するようにします。
- これにより、知識のネットワーク（グラフ）のノードが確実に作成され、ユーザーが後から加筆しやすい状態（Wikipedia のような挙動）になります。

### 3. TDD によるテスト補強
- **`test_all.py`**: Auto-linking（自動リンク付与関数）のユニットテストを追加します。
- **`tests/rebuild_test.py`**: 現在「警告 (Warning)」に留めている `concepts/` ディレクトリ下のファイル生成チェックを「必須 (Error)」に変更し、概念ページが生成されない場合はテストが失敗するように修正します。

---

## 修正対象コンポーネント

### `core/utils.py` (NEW)
#### [MODIFY] [core/utils.py](file:///f:/PythonScripit/md-wiki/core/utils.py)
- 本文中のテキストを自動リンク化する関数 `auto_link_concepts(body: str, concepts: List[str]) -> str` を新規実装。

### `agent/graph.py`
#### [MODIFY] [agent/graph.py](file:///f:/PythonScripit/md-wiki/agent/graph.py)
- `draft_node`: Step 2 完了後、`proposed_data["body"] = auto_link_concepts(clean_body, metadata.concepts)` を呼び出し。
- `lint_node`: `evidences` が空の場合でも、LLM の事前知識を活用して短い概念解説（スタブ）を生成して `create_draft_from_schema` を呼び出すようにフォールバックを追加。

### `tests/test_all.py`
#### [MODIFY] [tests/test_all.py](file:///f:/PythonScripit/md-wiki/tests/test_all.py)
- `TestAutoLinkConcepts` クラスを追加し、既存の Markdown 構造（見出しや既にリンク化されている部分）を破壊せずに自動リンクが付与されるかを検証するユニットテストを記述。

### `tests/rebuild_test.py`
#### [MODIFY] [tests/rebuild_test.py](file:///f:/PythonScripit/md-wiki/tests/rebuild_test.py)
- `concepts` ディレクトリ内にページが 1 つも生成されない場合を「エラー」とし、テストが失敗するように厳格化。

---

## 期待される結果
- 生成される Wiki ページに `[[ ]]` の用語リンクが大量に復活し、高密度な知識ネットワークが形成される。
- `uv run python main.py --lint` 実行時に、未定義のリンクに対応する概念ページが `wiki/concepts/` 下に確実に生成される。
- これにより `main` ブランチ以上の知識拡張能力を取り戻す。

## ユーザー承認事項
上記のアプローチ（プログラム的な Auto-linking と Lint 時のスタブ生成）で実装を進めてよろしいでしょうか？承認いただければ、まずテストコードの作成 (TDD) から着手します。
