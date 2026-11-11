"""网页提取记录模型。"""

from __future__ import annotations

import json

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from ..utils.time import now_iso


class WebExtraction(Base):
    """一次网页正文提取的结果快照。"""

    __tablename__ = "web_extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, default="")
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    images: Mapped[str] = mapped_column(Text, default="[]")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="ok", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso, index=True)

    __table_args__ = (Index("ix_web_extractions_time", "created_at"),)

    @property
    def images_list(self) -> list[str]:
        try:
            value = json.loads(self.images or "[]")
            return [str(item) for item in value] if isinstance(value, list) else []
        except ValueError:
            return []

    @images_list.setter
    def images_list(self, value: list[str]) -> None:
        self.images = json.dumps(value[:60], ensure_ascii=False)
