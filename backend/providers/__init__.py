"""外部能力提供者包。

导入本包会自动注册所有内置引擎，业务层只需使用 ``registry`` 中的
``get_ocr`` / ``get_ai`` 获取实例。
"""

from . import ai, ocr  # noqa: F401  注册内置引擎
from .base import (
    AIProvider,
    AIResult,
    ChatMessage,
    CredentialField,
    OCRProvider,
    OCRResult,
    ProviderError,
    TextBlock,
)
from .registry import (
    ai_catalog,
    ai_providers,
    get_ai,
    get_ocr,
    ocr_catalog,
    ocr_providers,
)

__all__ = [
    "AIProvider",
    "AIResult",
    "ChatMessage",
    "CredentialField",
    "OCRProvider",
    "OCRResult",
    "ProviderError",
    "TextBlock",
    "ai_catalog",
    "ai_providers",
    "get_ai",
    "get_ocr",
    "ocr_catalog",
    "ocr_providers",
]
