"""通用数据结构。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageResponse(BaseModel):
    """简单消息响应。"""

    ok: bool = True
    message: str = ""
    detail: dict | None = None


class PageMeta(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int = 0
    pages: int = 0


class Page(BaseModel, Generic[T]):
    """分页响应。"""

    items: list[T] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


class ErrorBody(BaseModel):
    """统一错误结构。"""

    detail: str
    code: str = "error"
    hint: str | None = None
