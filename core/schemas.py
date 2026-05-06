"""
Pydantic スキーマ定義。

設計方針:
  - WikiMetadataSchema: タグ・エイリアス等の「構造的に扱うべき」メタデータのみ。
    → with_structured_output で確実に取得する。
  - WikiPageSchema: 従来互換。全フィールドを含むが、主にlint_node等で使用。
  - body (本文) は自由形式の Markdown であり、Pydantic で制約しない。
"""
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator

class WikiMetadataSchema(BaseModel):
    """記事メタデータのみを構造化するスキーマ。
    
    LLM が生成した自由形式の Markdown 本文から、
    タグ・エイリアス等のメタデータだけを抽出する目的で使用する。
    """
    title: str = Field(description="Wikiページのタイトル")
    abstract: str = Field(description="3行以内の全体概要")
    concepts: List[str] = Field(description="本文中の主要な概念や用語のリスト")
    tags: List[str] = Field(description="分類タグのリスト（短く、スペースを含まない）")
    aliases: Optional[List[str]] = Field(default_factory=list, description="別名や略称のリスト")

class WikiPageSchema(BaseModel):
    """Wikiページ全体の構造を定義するスキーマ（従来互換）。
    
    lint_node 等、本文も含めて一括生成する場面で使用する。
    """
    title: str = Field(description="Wikiページのタイトル（H1見出しに使用）")
    abstract: str = Field(description="3行以内の全体概要（[!abstract]コールアウトに使用）")
    concepts: List[str] = Field(description="主要な概念や貢献のリスト")
    body: str = Field(description="詳細な解説本文（Markdown形式、内部リンクを含む）")
    tags: List[str] = Field(description="関連タグのリスト（スペースを含まない）")
    aliases: Optional[List[str]] = Field(default_factory=list, description="別名や略称のリスト")

class UpdateDecisionSchema(BaseModel):
    """既存ページの更新が必要かどうかの判定結果。"""
    update_needed: bool = Field(description="更新が必要な場合はTrue、不要な場合はFalse")
    reason: str = Field(description="その判定に至った理由")

class WikiFrontmatterSchema(BaseModel):
    """Obsidian の YAML Frontmatter を定義する厳密なスキーマ。"""
    tags: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    abstract: Optional[str] = Field(default=None)
    type: str = Field(default="wiki")
    created: Optional[str] = Field(default=None)
    updated: Optional[str] = Field(default=None)
    sources: List[str] = Field(default_factory=list)

    @field_validator("abstract", mode="before")
    @classmethod
    def _check_abstract(cls, v: Any) -> str:
        if not v or v in ["---", "自動生成スタブ", "None", "要約なし"]:
            # 無意味な値は空にする（再生成を促すため、あるいはデフォルト値を入れる）
            return "本文を参照してください（要約抽出中）。"
        if isinstance(v, str) and len(v) < 10:
            return f"{v}（詳細な要約が不足しています）"
        return v

    @field_validator("tags", "aliases", "sources", mode="before")
    @classmethod
    def _ensure_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            # カンマ区切り、または単一文字列をリスト化
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    class Config:
        extra = "allow" # 予期せぬフィールドも一旦保持する（破壊防止）
