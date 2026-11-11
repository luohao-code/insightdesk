"""批量任务接口，包含 SSE 实时进度。"""

from __future__ import annotations

import asyncio
import json
import queue
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import BatchRecognizeRequest, RetryRequest
from ..services import serializers, settings_service, task_service
from ..services.events import bus
from ..services.task_service import TaskError
from ..utils.time import now_iso

router = APIRouter(prefix="/tasks", tags=["批量任务"])


@router.post("/batches", summary="创建批量识别任务")
def create_batch(payload: BatchRecognizeRequest, db: Session = Depends(get_db)):
    settings = settings_service.get_all(db)
    items = [{"image_id": item.image_id, "filename": item.filename} for item in payload.images]
    options = {"language": payload.language, "merge_lines": payload.merge_lines}
    try:
        batch, accepted, rejected, note = task_service.create_batch(
            db,
            items,
            settings,
            name=payload.name,
            engine=payload.engine,
            options=options,
            concurrency=payload.concurrency,
        )
    except TaskError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"创建批次失败：{exc}") from exc

    return {
        "batch": serializers.batch_out(batch),
        "accepted": accepted,
        "rejected": rejected,
        "notice": note,
    }


@router.get("/batches", summary="批次列表")
def list_batches(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    db: Session = Depends(get_db),
):
    items, total = task_service.list_batches(db, limit=limit, offset=offset, status=status)
    return {"items": [serializers.batch_out(item) for item in items], "total": total}


@router.get("/batches/{batch_id}", summary="批次详情")
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    try:
        batch = task_service.get_batch(db, batch_id)
    except TaskError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serializers.batch_detail(batch)


@router.post("/batches/{batch_id}/retry", summary="重试失败任务")
def retry_batch(batch_id: int, payload: RetryRequest | None = None, db: Session = Depends(get_db)):
    try:
        batch = task_service.retry_failed(
            db, batch_id, payload.task_ids if payload else None
        )
    except TaskError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "batch": serializers.batch_out(batch)}


@router.post("/batches/{batch_id}/cancel", summary="取消批次")
def cancel_batch(batch_id: int, db: Session = Depends(get_db)):
    try:
        batch = task_service.cancel_batch(db, batch_id)
    except TaskError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "batch": serializers.batch_out(batch)}


@router.get("/summary", summary="任务运行摘要")
def summary(db: Session = Depends(get_db)):
    return {
        "active_batches": task_service.active_batch_count(),
        "active_ids": task_service.active_executors(),
        "subscribers": bus.subscriber_count,
        "time": now_iso(),
    }


@router.get("/stream", summary="SSE 进度流")
async def stream(request: Request, batch_id: int | None = None):
    """Server-Sent Events 进度流。

    前端使用 ``EventSource`` 订阅；连接断开由浏览器自动重连。
    服务端每 15 秒发送一次注释心跳，避免中间代理断开空闲连接。
    """

    async def event_generator():
        subscriber = bus.subscribe()
        try:
            yield "retry: 3000\n\n"
            yield 'event: ready\ndata: {"ok": true}\n\n'
            last_ping = time.time()
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = subscriber.get_nowait()
                except queue.Empty:
                    if time.time() - last_ping > 15:
                        last_ping = time.time()
                        yield ": ping\n\n"
                    await asyncio.sleep(0.35)
                    continue

                if batch_id is not None:
                    batch = event.get("batch") or {}
                    if batch.get("id") != batch_id:
                        continue

                payload = json.dumps(event, ensure_ascii=False)
                yield f"event: {event.get('type', 'message')}\ndata: {payload}\n\n"
                last_ping = time.time()
        finally:
            bus.unsubscribe(subscriber)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
