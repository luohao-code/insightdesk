"""模型到 API 视图的序列化。

集中处理 URL 拼接、标签解析与字段裁剪，避免各路由重复实现。
"""

from __future__ import annotations

from ..models import Batch, Document, Task, WebExtraction
from ..utils.text import truncate


def upload_url(image_id: str) -> str:
    return f"/api/media/upload/{image_id}"


def upload_thumb_url(image_id: str) -> str:
    return f"/api/media/upload/{image_id}/thumb"


def document_out(document: Document, *, full: bool = True) -> dict:
    payload = {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "source_type": document.source_type,
        "source_url": document.source_url,
        "content": document.content if full else "",
        "original_content": document.original_content if full else "",
        "excerpt": truncate(document.content, 140),
        "engine": document.engine,
        "language": document.language,
        "confidence": round(document.confidence or 0.0, 3),
        "char_count": document.char_count,
        "status": document.status,
        "error": document.error,
        "batch_id": document.batch_id,
        "tags": document.tags_list,
        "favorite": bool(document.favorite),
        "version": document.version,
        "meta": document.meta_dict,
        "image_url": f"/api/media/document/{document.id}/image" if document.image_path else None,
        "thumbnail_url": f"/api/media/document/{document.id}/thumb" if document.thumb_path else None,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }
    return payload


def task_out(task: Task) -> dict:
    return {
        "id": task.id,
        "filename": task.filename,
        "status": task.status,
        "attempts": task.attempts,
        "error": task.error,
        "duration_ms": round(task.duration_ms or 0.0, 1),
        "document_id": task.document_id,
        "image_url": f"/api/media/task/{task.id}/image" if task.image_path else None,
        "thumbnail_url": f"/api/media/task/{task.id}/thumb" if task.image_path else None,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
    }


def batch_out(batch: Batch) -> dict:
    return {
        "id": batch.id,
        "name": batch.name,
        "status": batch.status,
        "total": batch.total,
        "succeeded": batch.succeeded,
        "failed": batch.failed,
        "concurrency": batch.concurrency,
        "engine": batch.engine,
        "progress": batch.progress,
        "message": batch.message,
        "created_at": batch.created_at,
        "started_at": batch.started_at,
        "finished_at": batch.finished_at,
    }


def batch_detail(batch: Batch) -> dict:
    payload = batch_out(batch)
    payload["tasks"] = [task_out(task) for task in batch.tasks]
    return payload


def web_out(record: WebExtraction) -> dict:
    return {
        "id": record.id,
        "url": record.url,
        "title": record.title,
        "site": record.site,
        "word_count": record.word_count,
        "status": record.status,
        "created_at": record.created_at,
    }
