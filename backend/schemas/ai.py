"""AI 相关结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AIProcessRequest(BaseModel):
    action: str = Field(description="translate/summarize/keywords/qa/polish/outline")
    document_id: int | None = None
    text: str | None = None
    provider: str | None = None
    model: str | None = None
    options: dict = Field(default_factory=dict)
    save: bool = True


class AIProcessResponse(BaseModel):
    run_id: int | None = None
    action: str
    output: str
    provider: str
    provider_label: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    demo: bool = False
    notice: str | None = None
    truncated: bool = False
    document_id: int | None = None


class ChatMessageIn(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    document_id: int | None = None
    message: str = Field(min_length=1, max_length=20000)
    provider: str | None = None
    model: str | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ConversationOut(BaseModel):
    id: int
    title: str
    document_id: int | None = None
    messages: list[MessageOut] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ChatResponse(BaseModel):
    conversation: ConversationOut
    reply: MessageOut
    provider: str
    model: str
    demo: bool = False
    latency_ms: float = 0.0


class AIProviderInfo(BaseModel):
    name: str
    label: str
    description: str
    requires_credentials: bool
    available: bool
    reason: str
    default_base_url: str = ""
    models: list[str] = Field(default_factory=list)
    credential_fields: list[dict] = Field(default_factory=list)
