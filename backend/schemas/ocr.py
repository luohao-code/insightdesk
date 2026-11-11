"""OCR 相关请求/响应结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class UploadedImage(BaseModel):
    """已上传图片的元信息。"""

    id: str
    filename: str
    width: int
    height: int
    size_bytes: int
    format: str
    url: str
    thumbnail_url: str
    uploaded_at: str


class UploadResponse(BaseModel):
    images: list[UploadedImage] = Field(default_factory=list)
    rejected: list[dict] = Field(default_factory=list)


class RecognizeRequest(BaseModel):
    """单图识别请求。"""

    image_id: str = Field(min_length=4, max_length=64)
    engine: str | None = None
    language: str = "auto"
    grayscale: bool = False
    autocontrast: bool = False
    rotate: float = 0.0
    max_long_edge: int = 2400
    save: bool = True
    merge_lines: bool = True


class OCRBlockOut(BaseModel):
    text: str
    confidence: float | None = None
    box: list[list[float]] | None = None


class RecognizeResponse(BaseModel):
    """单图识别结果。"""

    document_id: int | None = None
    text: str
    blocks: list[OCRBlockOut] = Field(default_factory=list)
    engine: str
    engine_label: str
    confidence: float
    duration_ms: float
    char_count: int
    language: str
    demo: bool = False
    notice: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None


class BatchRecognizeItem(BaseModel):
    """批量请求中的一项。"""

    image_id: str
    filename: str | None = None


class BatchRecognizeRequest(BaseModel):
    images: list[BatchRecognizeItem]
    engine: str | None = None
    language: str = "auto"
    merge_lines: bool = True
    name: str | None = None
    concurrency: int | None = None


class EngineInfo(BaseModel):
    name: str
    label: str
    description: str
    requires_credentials: bool
    available: bool
    reason: str
    credential_fields: list[dict] = Field(default_factory=list)
    supports_language: list[str] = Field(default_factory=list)
