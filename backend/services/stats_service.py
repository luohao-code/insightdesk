"""统计看板服务。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AIRun, Batch, Document, Task, WebExtraction
from ..utils.time import now, now_iso, recent_days
from . import history_service

_TASK_FAILED_STATES = {"failed", "cancelled"}


def overview(db: Session) -> dict:
    documents = db.scalar(select(func.count(Document.id))) or 0
    total_chars = db.scalar(select(func.sum(Document.char_count))) or 0
    favorites = db.scalar(select(func.count(Document.id)).where(Document.favorite.is_(True))) or 0
    batches = db.scalar(select(func.count(Batch.id))) or 0
    running = db.scalar(
        select(func.count(Batch.id)).where(Batch.status.in_(("queued", "running")))
    ) or 0
    ai_runs = db.scalar(select(func.count(AIRun.id))) or 0
    web_count = db.scalar(select(func.count(WebExtraction.id))) or 0

    today_start = now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_documents = db.scalar(
        select(func.count(Document.id)).where(Document.created_at >= today_start)
    ) or 0

    succeeded = db.scalar(select(func.count(Task.id)).where(Task.status == "succeeded")) or 0
    failed = db.scalar(select(func.count(Task.id)).where(Task.status == "failed")) or 0
    finished_total = succeeded + failed
    success_rate = round(succeeded / finished_total * 100, 1) if finished_total else 0.0

    avg_task_ms = db.scalar(
        select(func.avg(Task.duration_ms)).where(Task.status == "succeeded", Task.duration_ms > 0)
    )
    avg_task_ms = round(float(avg_task_ms or 0), 1)

    engine_rows = db.execute(
        select(Document.engine, func.count(Document.id))
        .where(Document.source_type == "image")
        .group_by(Document.engine)
        .order_by(func.count(Document.id).desc())
    ).all()
    engine_usage = [{"engine": str(engine or "unknown"), "count": int(count)} for engine, count in engine_rows]

    source_rows = db.execute(
        select(Document.source_type, func.count(Document.id))
        .group_by(Document.source_type)
        .order_by(func.count(Document.id).desc())
    ).all()
    source_usage = [{"source": str(source or "unknown"), "count": int(count)} for source, count in source_rows]

    day_rows = dict(
        db.execute(
            select(func.substr(Document.created_at, 1, 10), func.count(Document.id))
            .group_by(func.substr(Document.created_at, 1, 10))
        ).all()
    )
    trend = [{"date": day, "count": int(day_rows.get(day, 0))} for day in recent_days(7)]

    return {
        "documents": int(documents),
        "total_chars": int(total_chars),
        "favorites": int(favorites),
        "batches": int(batches),
        "running_batches": int(running),
        "ai_runs": int(ai_runs),
        "web_extractions": int(web_count),
        "today_documents": int(today_documents),
        "success_rate": success_rate,
        "avg_task_ms": avg_task_ms,
        "engine_usage": engine_usage,
        "source_usage": source_usage,
        "trend": trend,
        "recent": history_service.recent(db, limit=6),
        "generated_at": now_iso(),
    }
