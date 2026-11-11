"""健康检查与运行信息接口。"""

from __future__ import annotations

import platform
import sys
import time
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..services import cleanup, ocr_service, settings_service, task_service
from ..services.events import bus
from ..utils.time import now_iso

router = APIRouter(tags=["系统"])

_STARTED_AT = time.time()


@router.get("/health", summary="健康检查")
def health(db: Session = Depends(get_db)) -> dict:
    database_status = "ok"
    database_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - 数据库异常
        database_status = "error"
        database_error = str(exc)

    settings = settings_service.get_all(db)
    engines = ocr_service.health(settings)
    overall = "ok" if database_status == "ok" and engines["available"] else "degraded"

    return {
        "status": overall,
        "app": config.APP_NAME,
        "version": config.VERSION,
        "database": {"status": database_status, "error": database_error},
        "engines": engines,
        "desktop_mode": config.is_desktop_mode(),
        "uptime_seconds": round(time.time() - _STARTED_AT, 1),
        "time": now_iso(),
    }


@router.get("/system/info", summary="系统运行信息")
def system_info(db: Session = Depends(get_db)) -> dict:
    settings = settings_service.get_all(db)
    return {
        "app": config.APP_NAME,
        "version": config.VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "data_dir": str(config.DATA_DIR),
        "desktop_mode": config.is_desktop_mode(),
        "started_at": datetime.fromtimestamp(_STARTED_AT).isoformat(),
        "uptime_seconds": round(time.time() - _STARTED_AT, 1),
        "active_batches": task_service.active_batch_count(),
        "sse_subscribers": bus.subscriber_count,
        "storage": cleanup.disk_usage(),
        "uploads": cleanup.uploads_summary(),
        "engines": {
            "ocr_default": settings.get("ocr_engine"),
            "ai_default": settings.get("ai_provider"),
            "ai_model": settings.get("ai_model"),
        },
    }


@router.post("/system/cleanup", summary="清理过期上传文件")
def cleanup_files(days: int | None = None, dry_run: bool = False, db: Session = Depends(get_db)) -> dict:
    result = cleanup.cleanup_uploads(db, days=days, dry_run=dry_run)
    return {"ok": True, **result}


@router.get("/system/logs", summary="查看最近运行日志")
def recent_logs(lines: int = 200) -> dict:
    path = config.LOG_DIR / "app.log"
    if not path.exists():
        return {"lines": [], "path": str(path)}
    limit = max(1, min(1000, lines))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        content = handle.readlines()[-limit:]
    return {"lines": [line.rstrip("\n") for line in content], "path": str(path)}
