"""网页提取相关结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebExtractRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2048)
    save: bool = True
    auto_open: bool | None = None
    to_document: bool = False


class WebExtractResponse(BaseModel):
    id: int | None = None
    url: str
    final_url: str
    title: str = ""
    author: str | None = None
    site: str | None = None
    published_at: str | None = None
    content: str = ""
    summary: str = ""
    images: list[str] = Field(default_factory=list)
    word_count: int = 0
    elapsed_ms: float = 0.0
    auto_opened: bool = False
    document_id: int | None = None
    notice: str | None = None


class WebOpenRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2048)


class WebOpenResponse(BaseModel):
    ok: bool = True
    opened: bool = False
    mode: str = "browser"
    message: str = ""


class WebHistoryItem(BaseModel):
    id: int
    url: str
    title: str
    site: str | None = None
    word_count: int = 0
    status: str
    created_at: str
