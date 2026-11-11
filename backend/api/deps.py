"""API 层公共依赖。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..db import get_db
from ..services import settings_service

__all__ = ["get_db", "get_settings"]


def get_settings(db: Session) -> dict:
    """获取包含密钥明文的完整设置（仅服务端内部使用）。"""

    return settings_service.get_all(db)
