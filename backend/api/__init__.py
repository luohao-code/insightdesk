"""API 路由集合。"""

from fastapi import APIRouter

from . import (
    routes_ai,
    routes_export,
    routes_health,
    routes_history,
    routes_media,
    routes_ocr,
    routes_settings,
    routes_stats,
    routes_system,
    routes_tasks,
    routes_web,
)

api_router = APIRouter()
api_router.include_router(routes_health.router)
api_router.include_router(routes_system.router)
api_router.include_router(routes_ocr.router)
api_router.include_router(routes_media.router)
api_router.include_router(routes_tasks.router)
api_router.include_router(routes_ai.router)
api_router.include_router(routes_history.router)
api_router.include_router(routes_export.router)
api_router.include_router(routes_web.router)
api_router.include_router(routes_settings.router)
api_router.include_router(routes_stats.router)

__all__ = ["api_router"]
