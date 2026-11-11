"""引擎注册表。

业务层通过名称获取引擎实例，并列出当前环境下的可用性，
设置页据此渲染可选项与缺失凭据提示。
"""

from __future__ import annotations

from .base import AIProvider, OCRProvider

_OCR_PROVIDERS: dict[str, OCRProvider] = {}
_AI_PROVIDERS: dict[str, AIProvider] = {}


def register_ocr(provider: OCRProvider) -> OCRProvider:
    if not provider.name:
        raise ValueError("OCR 引擎必须声明 name")
    _OCR_PROVIDERS[provider.name] = provider
    return provider


def register_ai(provider: AIProvider) -> AIProvider:
    if not provider.name:
        raise ValueError("AI 引擎必须声明 name")
    _AI_PROVIDERS[provider.name] = provider
    return provider


def get_ocr(name: str | None) -> OCRProvider:
    provider = _OCR_PROVIDERS.get(name or "")
    if provider is None:
        raise KeyError(f"未知的 OCR 引擎：{name}")
    return provider


def get_ai(name: str | None) -> AIProvider:
    provider = _AI_PROVIDERS.get(name or "")
    if provider is None:
        raise KeyError(f"未知的 AI 引擎：{name}")
    return provider


def ocr_providers() -> dict[str, OCRProvider]:
    return dict(_OCR_PROVIDERS)


def ai_providers() -> dict[str, AIProvider]:
    return dict(_AI_PROVIDERS)


def ocr_catalog(settings: dict) -> list[dict]:
    """返回 OCR 引擎目录，包含可用性与凭据字段描述。"""

    catalog = []
    for provider in _OCR_PROVIDERS.values():
        available, reason = provider.available(settings)
        catalog.append(
            {
                "name": provider.name,
                "label": provider.label,
                "description": provider.description,
                "requires_credentials": provider.requires_credentials,
                "available": available,
                "reason": reason,
                "credential_fields": [
                    {
                        "key": field.key,
                        "label": field.label,
                        "secret": field.secret,
                        "placeholder": field.placeholder,
                        "help_text": field.help_text,
                    }
                    for field in provider.credential_fields
                ],
                "supports_language": list(provider.supports_language),
            }
        )
    return catalog


def ai_catalog(settings: dict) -> list[dict]:
    catalog = []
    for provider in _AI_PROVIDERS.values():
        available, reason = provider.available(settings)
        catalog.append(
            {
                "name": provider.name,
                "label": provider.label,
                "description": provider.description,
                "requires_credentials": provider.requires_credentials,
                "available": available,
                "reason": reason,
                "default_base_url": provider.default_base_url,
                "models": list(provider.models),
                "credential_fields": [
                    {
                        "key": field.key,
                        "label": field.label,
                        "secret": field.secret,
                        "placeholder": field.placeholder,
                        "help_text": field.help_text,
                    }
                    for field in provider.credential_fields
                ],
            }
        )
    return catalog
