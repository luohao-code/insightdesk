"""外部 HTTP 调用的轻量封装。

统一处理：超时、重试、错误信息归一化。
只依赖 ``requests``，不引入额外运行时。
"""

from __future__ import annotations

import time

import requests

from .base import ProviderError

DEFAULT_TIMEOUT = (5, 45)


def _friendly_error(response: requests.Response) -> str:
    """从响应中提取尽量可读的错误描述。"""

    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        for key in ("error_msg", "message", "Message", "msg", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value[:300]
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"][:300]
    text = (response.text or "").strip().replace("\n", " ")
    return text[:300] or f"HTTP {response.status_code}"


def request_json(
    method: str,
    url: str,
    *,
    timeout: tuple[int, int] = DEFAULT_TIMEOUT,
    retries: int = 1,
    retry_backoff: float = 1.2,
    **kwargs,
) -> dict:
    """发起 HTTP 请求并返回 JSON。

    :raises ProviderError: 网络异常、非 2xx、响应非 JSON
    """

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.Timeout as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_backoff ** attempt)
                continue
            raise ProviderError("请求超时，请检查网络或稍后重试", code="timeout", retryable=True) from exc
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_backoff ** attempt)
                continue
            raise ProviderError(f"网络请求失败：{exc}", code="network", retryable=True) from exc

        if response.status_code == 429 or response.status_code >= 500:
            if attempt < retries:
                time.sleep(retry_backoff ** attempt)
                continue
            raise ProviderError(
                f"服务暂不可用（HTTP {response.status_code}）：{_friendly_error(response)}",
                code="upstream",
                retryable=True,
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"调用失败（HTTP {response.status_code}）：{_friendly_error(response)}",
                code="http",
                retryable=response.status_code in (401, 403),
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("服务返回了非 JSON 响应", code="bad_response") from exc

    raise ProviderError(f"请求失败：{last_error}", code="unknown")
