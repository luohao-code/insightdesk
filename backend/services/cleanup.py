"""数据清理与启动维护。

* 按 ``keep_uploads_days`` 清理过期的上传原图与缩略图；
* 清理 OCR 预处理临时文件；
* 使用一个时间戳文件控制执行频率，避免每次启动都扫描磁盘。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from .. import config
from ..db import session_scope
from . import settings_service

logger = logging.getLogger(__name__)
_STATE_FILE = config.DATA_DIR / ".last_cleanup"


def cleanup_uploads(db: Session, *, days: int | None = None, dry_run: bool = False) -> dict:
    """删除超过保留期的上传文件，返回统计信息。"""

    keep_days = days if days is not None else settings_service.get_int(db, "keep_uploads_days", 30)
    cutoff = time.time() - max(1, keep_days) * 86400
    removed = 0
    freed = 0
    errors = 0

    for directory, suffix_filter in (
        (config.UPLOAD_DIR, (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif")),
        (config.THUMB_DIR, (".png",)),
    ):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if not path.is_file() or path.suffix.lower() not in suffix_filter:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime >= cutoff:
                continue
            freed += stat.st_size
            removed += 1
            if not dry_run:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    errors += 1

    # 预处理临时文件超过 1 天即可删除
    prepared = config.UPLOAD_DIR / "prepared"
    if prepared.exists():
        prepared_cutoff = time.time() - 86400
        for path in prepared.glob("*.png"):
            try:
                if path.stat().st_mtime < prepared_cutoff:
                    freed += path.stat().st_size
                    removed += 1
                    if not dry_run:
                        path.unlink(missing_ok=True)
            except OSError:
                errors += 1

    return {
        "removed": removed,
        "freed_bytes": freed,
        "keep_days": keep_days,
        "dry_run": dry_run,
        "errors": errors,
    }


def run_startup_maintenance() -> None:
    """启动维护：最多每 24 小时执行一次清理。"""

    try:
        if _STATE_FILE.exists() and time.time() - _STATE_FILE.stat().st_mtime < 86400:
            return
        with session_scope() as db:
            result = cleanup_uploads(db)
        _STATE_FILE.write_text(str(int(time.time())), encoding="utf-8")
        if result["removed"]:
            logger.info(
                "清理过期上传文件 %s 个，释放 %.1f MB",
                result["removed"],
                result["freed_bytes"] / 1024 / 1024,
            )
    except Exception as exc:  # pragma: no cover - 维护任务不应阻断启动
        logger.warning("启动维护失败：%s", exc)


def disk_usage() -> dict:
    """统计数据目录占用，供系统信息接口展示。"""

    total = 0
    files = 0
    for path in config.DATA_DIR.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
                files += 1
            except OSError:
                continue
    return {"bytes": total, "files": files, "path": str(config.DATA_DIR)}


def cleanup_response(db: Session, days: int | None = None) -> dict:
    return cleanup_uploads(db, days=days)


def uploads_summary() -> dict:
    """上传目录概览（不删除任何文件）。"""

    def summarize(directory: Path) -> dict:
        count = 0
        size = 0
        if directory.exists():
            for path in directory.iterdir():
                if path.is_file():
                    count += 1
                    try:
                        size += path.stat().st_size
                    except OSError:
                        pass
        return {"files": count, "bytes": size}

    return {
        "uploads": summarize(config.UPLOAD_DIR),
        "thumbs": summarize(config.THUMB_DIR),
        "exports": summarize(config.EXPORT_DIR),
    }
