"""批量任务相关结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: int
    filename: str
    status: str
    attempts: int
    error: str | None = None
    duration_ms: float = 0.0
    document_id: int | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class BatchOut(BaseModel):
    id: int
    name: str
    status: str
    total: int
    succeeded: int
    failed: int
    concurrency: int
    engine: str
    progress: float
    message: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class BatchDetail(BatchOut):
    tasks: list[TaskOut] = Field(default_factory=list)


class BatchListResponse(BaseModel):
    items: list[BatchOut] = Field(default_factory=list)
    total: int = 0


class BatchCreateResponse(BaseModel):
    batch: BatchOut
    accepted: int
    rejected: list[dict] = Field(default_factory=list)


class RetryRequest(BaseModel):
    task_ids: list[int] | None = None


class BatchProgressEvent(BaseModel):
    """SSE 推送的事件负载。"""

    type: str = "progress"
    batch_id: int
    status: str
    total: int
    succeeded: int
    failed: int
    progress: float
    message: str | None = None
    task: TaskOut | None = None
