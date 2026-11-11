"""历史记录相关结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: int
    title: str
    filename: str | None = None
    source_type: str
    source_url: str | None = None
    content: str
    original_content: str = ""
    excerpt: str = ""
    engine: str = ""
    language: str = "auto"
    confidence: float = 0.0
    char_count: int = 0
    status: str = "ok"
    error: str | None = None
    batch_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    favorite: bool = False
    version: int = 1
    meta: dict = Field(default_factory=dict)
    image_url: str | None = None
    thumbnail_url: str | None = None
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    items: list[DocumentOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 0
    took_ms: float = 0.0


class DocumentPatch(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    favorite: bool | None = None


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class HistoryStats(BaseModel):
    total: int = 0
    favorites: int = 0
    total_chars: int = 0
    engines: dict[str, int] = Field(default_factory=dict)
