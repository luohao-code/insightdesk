"""系统运维路由别名。

为避免与健康检查路由重复，这里仅保留空路由以便未来扩展
（例如备份恢复、缓存管理）。当前实现位于 :mod:`routes_health`。
"""

from fastapi import APIRouter

router = APIRouter(tags=["系统"])
