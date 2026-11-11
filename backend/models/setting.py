"""键值配置模型。"""

from __future__ import annotations

import json

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from ..utils.time import now_iso


class Setting(Base):
    """运行设置，以 JSON 字符串保存任意类型的值。"""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="null")
    updated_at: Mapped[str] = mapped_column(String(40), default=now_iso, onupdate=now_iso)

    @property
    def parsed(self):
        try:
            return json.loads(self.value)
        except (ValueError, TypeError):
            return None

    @parsed.setter
    def parsed(self, value) -> None:
        self.value = json.dumps(value, ensure_ascii=False)
