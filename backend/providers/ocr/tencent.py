"""腾讯云 OCR 适配。

接口：``GeneralBasicOCR``（通用印刷体识别）
文档：https://cloud.tencent.com/document/product/866/33526

腾讯云 API 采用 TC3-HMAC-SHA256 签名，本模块按照官方签名步骤实现，
不依赖官方 SDK，减少安装体积。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ...utils.images import image_to_base64
from ..base import CredentialField, OCRProvider, OCRResult, ProviderError, TextBlock
from ..http import request_json

_HOST = "ocr.tencentcloudapi.com"
_SERVICE = "ocr"
_ACTION = "GeneralBasicOCR"
_VERSION = "2018-11-19"


def _sha256_hex(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _sign(secret_id: str, secret_key: str, payload: str, timestamp: int) -> str:
    """计算 TC3-HMAC-SHA256 的 Authorization 头。"""

    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json; charset=utf-8"

    canonical_headers = f"content-type:{content_type}\nhost:{_HOST}\n"
    signed_headers = "content-type;host"
    canonical_request = (
        f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{_sha256_hex(payload)}"
    )

    credential_scope = f"{date}/{_SERVICE}/tc3_request"
    string_to_sign = (
        f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{_sha256_hex(canonical_request)}"
    )

    secret_date = _hmac_sha256(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, _SERVICE)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


class TencentOCRProvider(OCRProvider):
    name = "tencent"
    label = "腾讯云 OCR（云端）"
    description = "腾讯云通用印刷体识别，适合文档、截图等场景，需要 SecretId / SecretKey。"
    requires_credentials = True
    supports_language = ("auto", "zh", "en")
    credential_fields = (
        CredentialField(
            key="tencent_secret_id",
            label="SecretId",
            placeholder="腾讯云 API 密钥 SecretId",
            help_text="在访问管理 > API 密钥管理中创建",
        ),
        CredentialField(key="tencent_secret_key", label="SecretKey", placeholder="腾讯云 API 密钥 SecretKey"),
        CredentialField(
            key="tencent_region",
            label="地域",
            secret=False,
            placeholder="ap-guangzhou",
            help_text="OCR 服务地域，默认广州",
        ),
    )

    def available(self, settings: dict) -> tuple[bool, str]:
        if not settings.get("tencent_secret_id") or not settings.get("tencent_secret_key"):
            return False, "未配置腾讯云 SecretId / SecretKey"
        return True, "凭据已配置"

    def recognize(self, image_path: Path, settings: dict, options: dict | None = None) -> OCRResult:
        secret_id = str(settings.get("tencent_secret_id") or "")
        secret_key = str(settings.get("tencent_secret_key") or "")
        region = str(settings.get("tencent_region") or "ap-guangzhou")
        if not secret_id or not secret_key:
            raise ProviderError("缺少腾讯云 OCR 凭据", code="auth")

        started = time.perf_counter()
        payload = json.dumps({"ImageBase64": image_to_base64(image_path)}, ensure_ascii=False)
        timestamp = int(time.time())

        response = request_json(
            "POST",
            f"https://{_HOST}/",
            data=payload.encode("utf-8"),
            headers={
                "Authorization": _sign(secret_id, secret_key, payload, timestamp),
                "Content-Type": "application/json; charset=utf-8",
                "Host": _HOST,
                "X-TC-Action": _ACTION,
                "X-TC-Version": _VERSION,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Region": region,
            },
            timeout=(5, 60),
        )

        body = response.get("Response", {})
        if body.get("Error"):
            error = body["Error"]
            raise ProviderError(
                f"腾讯云 OCR 错误 {error.get('Code')}: {error.get('Message')}",
                code="upstream",
                retryable=str(error.get("Code", "")).startswith("Internal"),
            )

        blocks: list[TextBlock] = []
        for item in body.get("TextDetections", []) or []:
            text = str(item.get("DetectedText", "")).strip()
            if not text:
                continue
            polygon = item.get("ItemPolygon") or {}
            box = None
            if polygon:
                left = float(polygon.get("X", 0))
                top = float(polygon.get("Y", 0))
                width = float(polygon.get("Width", 0))
                height = float(polygon.get("Height", 0))
                box = [[left, top], [left + width, top], [left + width, top + height], [left, top + height]]
            blocks.append(
                TextBlock(
                    text=text,
                    confidence=round(float(item.get("Confidence", 0)) / 100, 3),
                    box=box,
                )
            )

        if not blocks:
            raise ProviderError("腾讯云 OCR 未识别到文字", code="empty_result")

        duration = (time.perf_counter() - started) * 1000
        confidences = [block.confidence for block in blocks if block.confidence is not None]
        return OCRResult(
            text="\n".join(block.text for block in blocks),
            blocks=blocks,
            engine=self.name,
            confidence=round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
            duration_ms=round(duration, 1),
            meta={"demo": False, "region": region, "request_id": body.get("RequestId")},
        )


provider = TencentOCRProvider()
