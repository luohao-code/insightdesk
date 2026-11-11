"""批量任务服务。

设计要点
--------
1. **并发可控**：每个批次一个线程池，最大并发由设置或创建参数决定（1–8）。
2. **失败重试**：单任务按指数退避重试，``attempts`` 持久化，重启后可追溯。
3. **实时进度**：每次状态变化写入数据库并通过事件总线广播，SSE 推送前端。
4. **可取消**：取消后未开始的任务标记为 cancelled，运行中的任务在执行前检查批次状态。
5. **可恢复**：服务异常重启后，将中断批次标记为 partial/failed，允许用户手动重试。
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Batch, Task
from ..providers import ProviderError
from ..utils.files import abs_path
from ..utils.time import now_iso
from . import image_service, ocr_service, serializers, settings_service
from .events import bus

logger = logging.getLogger(__name__)

_executors: dict[int, ThreadPoolExecutor] = {}
_state_lock = threading.RLock()
_finalize_locks: dict[int, threading.Lock] = {}


class TaskError(RuntimeError):
    """任务操作失败。"""


def _finalize_lock(batch_id: int) -> threading.Lock:
    with _state_lock:
        return _finalize_locks.setdefault(batch_id, threading.Lock())


def _publish(batch: Batch, *, event_type: str = "batch_update", task: Task | None = None) -> None:
    payload = {
        "type": event_type,
        "batch": serializers.batch_out(batch),
    }
    if task is not None:
        payload["task"] = serializers.task_out(task)
    bus.publish(payload)


def create_batch(
    db: Session,
    items: list[dict],
    settings: dict,
    *,
    name: str | None = None,
    engine: str | None = None,
    options: dict | None = None,
    concurrency: int | None = None,
) -> tuple[Batch, int, list[dict], str | None]:
    """创建批次并入队。

    :param items: ``[{"image_id": "...", "filename": "..."}]``
    :returns: ``(批次, 接收数量, 被拒绝项, 引擎降级说明)``
    """

    if not items:
        raise TaskError("没有待识别的图片")

    options = options or {}
    provider, note = ocr_service.resolve_engine(settings, engine)

    if concurrency is None:
        concurrency = settings_service.get_value(db, "concurrency", 3)
    try:
        concurrency = max(1, min(8, int(concurrency)))
    except (TypeError, ValueError):
        concurrency = 3

    batch = Batch(
        name=(name or f"批量识别 {now_iso()[:16].replace('T', ' ')}")[:255],
        status="queued",
        concurrency=concurrency,
        engine=provider.name,
        total=0,
        message=note,
    )
    batch.options_dict = options
    db.add(batch)
    db.flush()

    accepted = 0
    rejected: list[dict] = []
    for index, item in enumerate(items):
        image_id = str(item.get("image_id") or "")
        filename = str(item.get("filename") or image_id)
        try:
            path = image_service.get_path(image_id)
        except Exception as exc:
            rejected.append({"image_id": image_id, "filename": filename, "reason": str(exc)})
            continue
        task = Task(
            batch_id=batch.id,
            filename=filename[:255],
            image_path=image_service.relative(path),
            status="pending",
            order_index=index,
        )
        db.add(task)
        accepted += 1

    batch.total = accepted
    if accepted == 0:
        db.rollback()
        raise TaskError("所有图片均不可用：" + "；".join(item["reason"] for item in rejected[:3]))

    db.commit()
    db.refresh(batch)

    _publish(batch, event_type="batch_created")
    start_batch(batch.id)
    return batch, accepted, rejected, note


def start_batch(batch_id: int) -> None:
    """为批次的 pending 任务启动线程池。"""

    with session_scope() as db:
        batch = db.get(Batch, batch_id)
        if batch is None:
            return
        pending_ids = list(
            db.scalars(
                select(Task.id).where(Task.batch_id == batch_id, Task.status == "pending")
            ).all()
        )
        if not pending_ids:
            return
        batch.status = "running"
        batch.started_at = batch.started_at or now_iso()
        batch.message = None
        db.commit()
        concurrency = batch.concurrency
        _publish(batch)

    executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix=f"batch-{batch_id}")
    with _state_lock:
        _executors[batch_id] = executor

    for task_id in pending_ids:
        executor.submit(_run_task, batch_id, task_id)


def _run_task(batch_id: int, task_id: int) -> None:
    """执行单个任务项（在线程池中运行）。"""

    total_started = time.perf_counter()
    with session_scope() as db:
        settings = settings_service.get_all(db)
        max_retries = int(settings.get("max_retries", 2) or 0)
        backoff_base = float(settings.get("retry_backoff", 1.5) or 1.5)

    attempt = 0
    while True:
        attempt += 1
        with session_scope() as db:
            batch = db.get(Batch, batch_id)
            task = db.get(Task, task_id)
            if batch is None or task is None:
                return

            if batch.status == "cancelled":
                task.status = "cancelled"
                task.finished_at = now_iso()
                db.commit()
                _publish(batch, event_type="task_cancelled", task=task)
                _finalize_batch(batch_id)
                return

            task.status = "running"
            task.attempts = attempt
            task.started_at = task.started_at or now_iso()
            task.error = None
            image_path = abs_path(task.image_path)
            filename = task.filename
            options = batch.options_dict
            engine = batch.engine
            db.commit()
            _publish(batch, event_type="task_started", task=task)

        if image_path is None:
            error_message = "图片路径无效或文件已被清理"
            retryable = False
        else:
            try:
                with session_scope() as db:
                    settings = settings_service.get_all(db)
                    _result, document, _provider, _note = ocr_service.recognize_file(
                        db,
                        image_path=image_path,
                        filename=filename,
                        settings=settings,
                        engine=engine,
                        options=options,
                        save=True,
                    )
                duration = (time.perf_counter() - total_started) * 1000
                with session_scope() as db:
                    task = db.get(Task, task_id)
                    batch = db.get(Batch, batch_id)
                    if task is None or batch is None:
                        return
                    task.status = "succeeded"
                    task.document_id = document.id if document else None
                    task.duration_ms = round(duration, 1)
                    task.finished_at = now_iso()
                    task.error = None
                    # 原子自增，避免多个工作线程读到旧值导致计数丢失
                    db.execute(
                        update(Batch)
                        .where(Batch.id == batch_id)
                        .values(succeeded=Batch.succeeded + 1)
                    )
                    db.commit()
                    db.refresh(batch)
                    _publish(batch, event_type="task_succeeded", task=task)
                break
            except Exception as exc:  # 单任务失败不能影响其他任务
                error_message = str(exc) or exc.__class__.__name__
                retryable = not isinstance(exc, ProviderError) or exc.retryable
                logger.warning(
                    "批量任务失败 batch=%s task=%s attempt=%s: %s",
                    batch_id,
                    task_id,
                    attempt,
                    error_message,
                )

        if retryable and attempt <= max_retries:
            delay = backoff_base ** (attempt - 1)
            time.sleep(min(delay, 8.0))
            continue

        duration = (time.perf_counter() - total_started) * 1000
        with session_scope() as db:
            task = db.get(Task, task_id)
            batch = db.get(Batch, batch_id)
            if task is None or batch is None:
                return
            task.status = "failed"
            task.error = error_message[:800]
            task.duration_ms = round(duration, 1)
            task.finished_at = now_iso()
            if batch.status != "cancelled":
                db.execute(
                    update(Batch).where(Batch.id == batch_id).values(failed=Batch.failed + 1)
                )
            db.commit()
            db.refresh(batch)
            _publish(batch, event_type="task_failed", task=task)
        break

    _finalize_batch(batch_id)


def _finalize_batch(batch_id: int) -> None:
    """检查批次是否全部结束，并更新最终状态。"""

    lock = _finalize_lock(batch_id)
    if not lock.acquire(blocking=False):
        return
    try:
        with session_scope() as db:
            batch = db.get(Batch, batch_id)
            if batch is None:
                return
            remaining = db.scalar(
                select(func.count(Task.id)).where(
                    Task.batch_id == batch_id,
                    Task.status.in_(("pending", "running")),
                )
            )
            if remaining:
                return

            batch.finished_at = now_iso()
            if batch.status == "cancelled":
                batch.message = "任务已取消，可重试失败项"
            elif batch.failed == 0:
                batch.status = "succeeded"
                batch.message = "全部识别完成"
            elif batch.succeeded == 0:
                batch.status = "failed"
                batch.message = "全部任务失败，请检查引擎配置与图片质量"
            else:
                batch.status = "partial"
                batch.message = "部分任务失败，可点击重试失败项"
            db.commit()
            _publish(batch, event_type="batch_finished")
    finally:
        lock.release()
        with _state_lock:
            executor = _executors.pop(batch_id, None)
            _finalize_locks.pop(batch_id, None)
        if executor is not None:
            executor.shutdown(wait=False)


def cancel_batch(db: Session, batch_id: int) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise TaskError("批次不存在")
    if batch.is_finished:
        raise TaskError("批次已经结束，无需取消")

    batch.status = "cancelled"
    batch.message = "已请求取消"
    for task in batch.tasks:
        if task.status == "pending":
            task.status = "cancelled"
            task.finished_at = now_iso()
    db.commit()
    db.refresh(batch)
    _publish(batch, event_type="batch_cancelled")
    _finalize_batch(batch_id)
    return batch


def retry_failed(db: Session, batch_id: int, task_ids: list[int] | None = None) -> Batch:
    """重置失败任务并重新入队。"""

    batch = db.get(Batch, batch_id)
    if batch is None:
        raise TaskError("批次不存在")
    if batch.status in {"queued", "running"}:
        raise TaskError("批次正在执行，请等待结束或先取消")

    targets = [
        task
        for task in batch.tasks
        if task.status in {"failed", "cancelled"} and (task_ids is None or task.id in task_ids)
    ]
    if not targets:
        raise TaskError("没有可重试的任务")

    for task in targets:
        task.status = "pending"
        task.attempts = 0
        task.error = None
        task.duration_ms = 0.0
        task.started_at = None
        task.finished_at = None

    # 以实际状态重新计算失败数，避免并发累计造成偏差
    batch.failed = sum(1 for task in batch.tasks if task.status == "failed")
    batch.status = "queued"
    batch.finished_at = None
    batch.message = f"准备重试 {len(targets)} 个任务"
    db.commit()
    db.refresh(batch)

    _publish(batch, event_type="batch_retry")
    start_batch(batch_id)
    return batch


def list_batches(db: Session, *, limit: int = 30, offset: int = 0, status: str | None = None) -> tuple[list[Batch], int]:
    statement = select(Batch)
    counter = select(func.count(Batch.id))
    if status:
        statement = statement.where(Batch.status == status)
        counter = counter.where(Batch.status == status)
    total = db.scalar(counter) or 0
    items = list(
        db.scalars(statement.order_by(Batch.created_at.desc()).limit(limit).offset(offset)).all()
    )
    return items, total


def get_batch(db: Session, batch_id: int) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise TaskError("批次不存在")
    return batch


def recover_interrupted() -> int:
    """服务启动时处理中断的批次，返回受影响批次数。"""

    affected = 0
    with session_scope() as db:
        batches = list(
            db.scalars(select(Batch).where(Batch.status.in_(("queued", "running")))).all()
        )
        for batch in batches:
            interrupted = 0
            for task in batch.tasks:
                if task.status in {"pending", "running"}:
                    task.status = "failed"
                    task.error = "服务重启导致任务中断，请重试"
                    task.finished_at = now_iso()
                    interrupted += 1
            if interrupted:
                batch.failed += interrupted
                batch.status = "partial" if batch.succeeded else "failed"
                batch.message = "服务重启导致任务中断，可点击重试失败项"
                batch.finished_at = now_iso()
                affected += 1
        db.commit()
    if affected:
        logger.warning("已将 %s 个中断批次标记为可重试状态", affected)
    return affected


def active_batch_count() -> int:
    with _state_lock:
        return len(_executors)


def active_executors() -> list[int]:
    with _state_lock:
        return list(_executors.keys())
