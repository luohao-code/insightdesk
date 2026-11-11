"""设置与统计相关结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    values: dict
    secrets_masked: list[str] = Field(default_factory=list)
    engines: dict = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    values: dict


class ProviderTestRequest(BaseModel):
    kind: str = Field(description="ocr 或 ai")
    name: str


class ProviderTestResponse(BaseModel):
    ok: bool
    name: str
    label: str = ""
    latency_ms: float = 0.0
    message: str = ""


class OverviewStats(BaseModel):
    documents: int = 0
    total_chars: int = 0
    favorites: int = 0
    batches: int = 0
    running_batches: int = 0
    ai_runs: int = 0
    web_extractions: int = 0
    today_documents: int = 0
    success_rate: float = 0.0
    avg_task_ms: float = 0.0
    engine_usage: list[dict] = Field(default_factory=list)
    source_usage: list[dict] = Field(default_factory=list)
    trend: list[dict] = Field(default_factory=list)
    recent: list[dict] = Field(default_factory=list)
    generated_at: str = ""
