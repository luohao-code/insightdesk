"""OCR / AI 能力提供者的统一接口定义。

设计目标：**新增一个引擎只需要实现接口并注册**，业务层不感知具体实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class ProviderError(RuntimeError):
    """外部能力调用失败（网络、鉴权、额度、结果异常等）。"""

    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(slots=True)
class CredentialField:
    """引擎凭据字段的元数据，供设置页动态渲染。"""

    key: str
    label: str
    secret: bool = True
    placeholder: str = ""
    help_text: str = ""


@dataclass(slots=True)
class TextBlock:
    """识别出的一段文字。"""

    text: str
    confidence: float | None = None
    box: list[list[float]] | None = None
    page: int = 1


@dataclass(slots=True)
class OCRResult:
    """标准化的 OCR 结果。"""

    text: str
    blocks: list[TextBlock] = field(default_factory=list)
    engine: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0
    meta: dict = field(default_factory=dict)


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(slots=True)
class AIResult:
    """标准化的 AI 结果。"""

    text: str
    provider: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    meta: dict = field(default_factory=dict)


class OCRProvider(ABC):
    """OCR 引擎接口。"""

    name: str = ""
    label: str = ""
    description: str = ""
    requires_credentials: bool = False
    credential_fields: tuple[CredentialField, ...] = ()
    supports_language: tuple[str, ...] = ("auto", "zh", "en")

    @abstractmethod
    def available(self, settings: dict) -> tuple[bool, str]:
        """返回 ``(是否可用, 原因说明)``。"""

    @abstractmethod
    def recognize(self, image_path: Path, settings: dict, options: dict | None = None) -> OCRResult:
        """识别图片。失败时应抛出 :class:`ProviderError`。"""


class AIProvider(ABC):
    """大模型引擎接口。"""

    name: str = ""
    label: str = ""
    description: str = ""
    requires_credentials: bool = False
    default_base_url: str = ""
    models: tuple[str, ...] = ()
    credential_fields: tuple[CredentialField, ...] = ()

    @abstractmethod
    def available(self, settings: dict) -> tuple[bool, str]:
        """返回 ``(是否可用, 原因说明)``。"""

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        settings: dict,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResult:
        """执行一次对话补全。"""

    def process(
        self,
        action: str,
        text: str,
        system_prompt: str,
        user_prompt: str,
        settings: dict,
        *,
        model: str | None = None,
        options: dict | None = None,
    ) -> AIResult:
        """执行一次结构化处理。

        默认实现把提示词转换为对话消息后调用 :meth:`chat`。
        演示引擎可覆盖此方法，直接基于文本生成确定性结果。
        """

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]
        return self.chat(messages, settings, model=model)
