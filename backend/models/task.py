"""批量任务模型。"""

from __future__ import annotations

import json

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from ..utils.time import now_iso


class Batch(Base):
    """一次批量识别任务。"""

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), default="批量识别")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    # queued/running/succeeded/failed/partial/cancelled

    total: Mapped[int] = mapped_column(Integer, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)

    concurrency: Mapped[int] = mapped_column(Integer, default=3)
    engine: Mapped[str] = mapped_column(String(64), default="mock")
    options: Mapped[str] = mapped_column(Text, default="{}")

    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso, index=True)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="Task.order_index",
        lazy="selectin",
    )

    @property
    def options_dict(self) -> dict:
        try:
            value = json.loads(self.options or "{}")
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}

    @options_dict.setter
    def options_dict(self, value: dict) -> None:
        self.options = json.dumps(value, ensure_ascii=False)

    @property
    def progress(self) -> float:
        if not self.total:
            return 0.0
        return round((self.succeeded + self.failed) / self.total * 100, 1)

    @property
    def is_finished(self) -> bool:
        return self.status in {"succeeded", "failed", "partial", "cancelled"}


class Task(Base):
    """批次中的单个识别任务项。"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), default="")
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    # pending/running/succeeded/failed/cancelled

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    batch: Mapped[Batch] = relationship(back_populates="tasks")

    __table_args__ = (Index("ix_tasks_batch_status", "batch_id", "status"),)
