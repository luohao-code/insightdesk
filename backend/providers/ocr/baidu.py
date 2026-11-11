"""百度智能云 OCR 适配。

接口文档：https://cloud.baidu.com/doc/OCR/s/1k3h7y3db
使用「通用文字识别（高精度版）」``accurate_basic``，支持中英文混排。

凭据：API Key（client_id）与 Secret Key（client_secret）。
访问令牌缓存 29 天，失效时自动刷新一次。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from ...utils.images import image_to_base64
from ..base import CredentialField, OCRProvider, OCRResult, ProviderError, TextBlock
from ..http import request_json

_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
_TOKEN_LOCK = threading.Lock()


def _fetch_token(api_key: str, secret_key: str) -> str:
    payload = request_json(
        "POST",
        _TOKEN_URL,
        params={
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        },
        timeout=(5, 15),
    )
    token = payload.get("access_token")
    if not token:
        message = payload.get("error_description") or payload.get("error") or "未返回 access_token"
        raise ProviderError(f"百度 OCR 鉴权失败：{message}", code="auth")
    expires_in = int(payload.get("expires_in") or 2592000)
    _TOKEN_CACHE[api_key] = (token, time.time() + max(60, expires_in - 600))
    return token


def _get_token(api_key: str, secret_key: str) -> str:
    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get(api_key)
        if cached and cached[1] > time.time():
            return cached[0]
        return _fetch_token(api_key, secret_key)


class BaiduOCRProvider(OCRProvider):
    name = "baidu"
    label = "百度 OCR（云端）"
    description = "百度通用文字识别高精度版，中英文识别准确率高，需要 API Key。"
    requires_credentials = True
    supports_language = ("auto", "zh", "en")
    credential_fields = (
        CredentialField(
            key="baidu_api_key",
            label="API Key",
            placeholder="百度智能云应用的 API Key",
            help_text="在百度智能云控制台创建文字识别应用后获取",
        ),
        CredentialField(
            key="baidu_secret_key",
            label="Secret Key",
            placeholder="百度智能云应用的 Secret Key",
        ),
    )

    def available(self, settings: dict) -> tuple[bool, str]:
        if not settings.get("baidu_api_key") or not settings.get("baidu_secret_key"):
            return False, "未配置百度 OCR 的 API Key / Secret Key"
        return True, "凭据已配置"

    def recognize(self, image_path: Path, settings: dict, options: dict | None = None) -> OCRResult:
        api_key = str(settings.get("baidu_api_key") or "")
        secret_key = str(settings.get("baidu_secret_key") or "")
        if not api_key or not secret_key:
            raise ProviderError("缺少百度 OCR 凭据", code="auth")

        started = time.perf_counter()
        image_data = image_to_base64(image_path)
        language = (options or {}).get("language") or settings.get("ocr_language") or "auto"
        language_type = {"zh": "CHN_ENG", "en": "ENG", "auto": "CHN_ENG"}.get(language, "CHN_ENG")

        token = _get_token(api_key, secret_key)
        payload = self._call(token, image_data, language_type)
        if payload.get("error_code") in (110, 111):
            # 令牌失效，刷新后重试一次
            with _TOKEN_LOCK:
                _TOKEN_CACHE.pop(api_key, None)
            token = _get_token(api_key, secret_key)
            payload = self._call(token, image_data, language_type)

        if payload.get("error_code"):
            raise ProviderError(
                f"百度 OCR 返回错误 {payload.get('error_code')}：{payload.get('error_msg', '')}",
                code="upstream",
            )

        blocks = []
        for item in payload.get("words_result", []) or []:
            text = str(item.get("words", "")).strip()
            if not text:
                continue
            location = item.get("location") or {}
            box = None
            if location:
                left = float(location.get("left", 0))
                top = float(location.get("top", 0))
                width = float(location.get("width", 0))
                height = float(location.get("height", 0))
                box = [[left, top], [left + width, top], [left + width, top + height], [left, top + height]]
            blocks.append(TextBlock(text=text, confidence=0.95, box=box))

        if not blocks:
            raise ProviderError("百度 OCR 未识别到文字", code="empty_result")

        duration = (time.perf_counter() - started) * 1000
        return OCRResult(
            text="\n".join(block.text for block in blocks),
            blocks=blocks,
            engine=self.name,
            confidence=0.95,
            duration_ms=round(duration, 1),
            meta={"demo": False, "language": language_type, "log_id": payload.get("log_id")},
        )

    @staticmethod
    def _call(token: str, image_data: str, language_type: str) -> dict:
        return request_json(
            "POST",
            _OCR_URL,
            params={"access_token": token},
            data={
                "image": image_data,
                "language_type": language_type,
                "detect_direction": "true",
                "paragraph": "false",
                "probability": "true",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=(5, 60),
        )


provider = BaiduOCRProvider()
