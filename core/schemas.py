"""
Pydantic スキーマ定義。

設計方針:
  - WikiMetadataSchema: タグ・エイリアス等の「構造的に扱うべき」メタデータのみ。
    → with_structured_output で確実に取得する。
  - WikiPageSchema: 従来互換。全フィールドを含むが、主にlint_node等で使用。
  - WikiFrontmatterSchema: OKF v0.1 (Open Knowledge Format) 準拠。
    → Required: type, Recommended: title, description, resource, tags, timestamp
    → Extensions (producer-defined): aliases, concepts, created, sources
  - body (本文) は自由形式の Markdown であり、Pydantic で制約しない。
"""
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator

class WikiMetadataSchema(BaseModel):
    """記事メタデータのみを構造化するスキーマ。
    
    LLM が生成した自由形式の Markdown 本文から、
    タグ・エイリアス等のメタデータだけを抽出する目的で使用する。
    """
    title: str = Field(description="Wikiページのタイトル")
    description: str = Field(description="1〜3行の概要（OKF description）")
    concepts: List[str] = Field(description="本文中の主要な概念や用語のリスト")
    tags: List[str] = Field(description="分類タグのリスト（短く、スペースを含まない）")
    aliases: Optional[List[str]] = Field(default_factory=list, description="別名や略称のリスト")

    # 後方互換: abstract プロパティ
    @property
    def abstract(self) -> Optional[str]:
        return self.description

    @model_validator(mode="before")
    @classmethod
    def _migrate_abstract(cls, data: Any) -> Any:
        if isinstance(data, dict) and "abstract" in data and "description" not in data:
            data["description"] = data.pop("abstract")
        return data

class WikiPageSchema(BaseModel):
    """Wikiページ全体の構造を定義するスキーマ（従来互換）。
    
    lint_node 等、本文も含めて一括生成する場面で使用する。
    """
    title: str = Field(description="Wikiページのタイトル（H1見出しに使用）")
    description: str = Field(description="1〜3行の概要（OKF description / [!abstract]コールアウトに使用）")
    concepts: List[str] = Field(description="主要な概念や貢献のリスト")
    body: str = Field(description="詳細な解説本文（Markdown形式、内部リンクを含む）")
    tags: List[str] = Field(description="関連タグのリスト（スペースを含まない）")
    aliases: Optional[List[str]] = Field(default_factory=list, description="別名や略称のリスト")

    # 後方互換: abstract プロパティ
    @property
    def abstract(self) -> Optional[str]:
        return self.description

    @model_validator(mode="before")
    @classmethod
    def _migrate_abstract(cls, data: Any) -> Any:
        if isinstance(data, dict) and "abstract" in data and "description" not in data:
            data["description"] = data.pop("abstract")
        return data

class UpdateDecisionSchema(BaseModel):
    """既存ページの更新が必要かどうかの判定結果。"""
    update_needed: bool = Field(description="更新が必要な場合はTrue、不要な場合はFalse")
    reason: str = Field(description="その判定に至った理由")

class WikiFrontmatterSchema(BaseModel):
    """OKF v0.1 (Open Knowledge Format) 準拠の YAML Frontmatter スキーマ。
    
    OKF Required: type
    OKF Recommended: title, description, resource, tags, timestamp
    md-wiki Extensions (producer-defined): aliases, concepts, created, sources
    """
    # --- OKF Required (§4.1) ---
    type: str = Field(default="Concept", description="OKF concept type")

    # --- OKF Recommended (§4.1, priority order) ---
    title: Optional[str] = Field(default=None, description="Human-readable display name")
    description: Optional[str] = Field(default=None, description="One-line summary (旧 abstract)")
    resource: Optional[str] = Field(default=None, description="Canonical URI for the underlying asset")
    tags: List[str] = Field(default_factory=list)
    timestamp: Optional[str] = Field(default=None, description="ISO 8601 last-modified (旧 updated)")

    # --- md-wiki Extensions (§4.1 Extensions, producer-defined) ---
    aliases: List[str] = Field(default_factory=list)
    concepts: List[str] = Field(default_factory=list)
    created: Optional[str] = Field(default=None)
    sources: List[str] = Field(default_factory=list)

    # 後方互換: abstract プロパティ (description のエイリアス)
    @property
    def abstract(self) -> Optional[str]:
        return self.description

    @abstract.setter
    def abstract(self, value: str):
        self.description = value

    # 後方互換: updated プロパティ (timestamp のエイリアス)
    @property
    def updated(self) -> Optional[str]:
        return self.timestamp

    @updated.setter
    def updated(self, value: str):
        self.timestamp = value

    @field_validator("description", mode="before")
    @classmethod
    def _check_description(cls, v: Any) -> str:
        if not v or v in ["---", "自動生成スタブ", "None", "要約なし"]:
            return "(自動生成スタブ: 本文の内容に基づき後日更新予定)"
        if isinstance(v, str) and len(v) < 10:
            return f"{v}（詳細な要約が不足しています）"
        return v

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        """レガシーフィールド名を OKF 準拠名にマイグレーションする。"""
        if isinstance(data, dict):
            # abstract → description
            if "abstract" in data and "description" not in data:
                data["description"] = data.pop("abstract")
            elif "abstract" in data and "description" in data:
                data.pop("abstract")  # description を優先
            # updated → timestamp
            if "updated" in data and "timestamp" not in data:
                data["timestamp"] = data.pop("updated")
            elif "updated" in data and "timestamp" in data:
                data.pop("updated")  # timestamp を優先
            # type: wiki → type: Article (レガシーマイグレーション)
            if data.get("type") == "wiki":
                data["type"] = "Article"
        return data

    @field_validator("tags", "aliases", "sources", "concepts", mode="before")
    @classmethod
    def _ensure_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            # カンマ区切り、または単一文字列をリスト化
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    class Config:
        extra = "allow"  # 予期せぬフィールドも一旦保持する（破壊防止、OKF §4.1 Extensions 準拠）

class DraftConfig(BaseModel):
    """create_draft_file 用の設定オブジェクト。"""
    page_name: str
    proposed_content: str
    source_filename: Optional[str] = None
    source_path: Optional[str] = None
    raw_markdown: Optional[str] = None
    sub_dir: Optional[str] = None
