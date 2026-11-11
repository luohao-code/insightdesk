"""文字资产（识别结果）模型。"""

from __future__ import annotations

import json

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from ..utils.time import now_iso


class Document(Base):
    """一条文字资产记录。

    既可以是图片 OCR 的结果，也可以来自网页提取或手工创建。
    编辑后的文本保存在 ``content``，原始识别文本保存在 ``original_content``，
    便于用户对比与恢复。
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="未命名文档")
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="image")  # image/web/manual/ai
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    content: Mapped[str] = mapped_column(Text, default="")
    original_content: Mapped[str] = mapped_column(Text, default="")

    engine: Mapped[str] = mapped_column(String(64), default="")
    language: Mapped[str] = mapped_column(String(32), default="auto")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(24), default="ok")  # ok/failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumb_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    tags: Mapped[str] = mapped_column(Text, default="[]")
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    meta: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[str] = mapped_column(String(40), default=now_iso, index=True)
    updated_at: Mapped[str] = mapped_column(String(40), default=now_iso, onupdate=now_iso)

    __table_args__ = (
        Index("ix_documents_source_type", "source_type"),
        Index("ix_documents_engine", "engine"),
        Index("ix_documents_status", "status"),
    )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    @property
    def tags_list(self) -> list[str]:
        try:
            value = json.loads(self.tags or "[]")
            return [str(item) for item in value] if isinstance(value, list) else []
        except ValueError:
            return []

    @tags_list.setter
    def tags_list(self, value: list[str]) -> None:
        self.tags = json.dumps(value, ensure_ascii=False)

    @property
    def meta_dict(self) -> dict:
        try:
            value = json.loads(self.meta or "{}")
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}

    @meta_dict.setter
    def meta_dict(self, value: dict) -> None:
        self.meta = json.dumps(value, ensure_ascii=False)

    @property
    def excerpt(self) -> str:
        text = (self.content or "").replace("\n", " ").strip()
        return text[:120] + ("…" if len(text) > 120 else "")

    def __repr__(self) -> str:  # pragma: no cover - 调试输出
        return f"<Document id={self.id} title={self.title!r} chars={self.char_count}>"
