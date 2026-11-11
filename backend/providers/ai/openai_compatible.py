"""OpenAI 兼容协议适配。

DeepSeek、Kimi（Moonshot）、智谱 GLM、通义千问等均提供
``/chat/completions`` 兼容接口，因此可以用同一份实现对接，
仅需切换 base_url、模型名与密钥。
"""

from __future__ import annotations

import time

from ..base import AIProvider, AIResult, ChatMessage, CredentialField, ProviderError
from ..http import request_json


class OpenAICompatibleProvider(AIProvider):
    """通用 OpenAI 兼容引擎。"""

    requires_credentials = True
    credential_fields = (
        CredentialField(
            key="ai_api_key",
            label="API Key",
            placeholder="粘贴对应平台的 API Key",
            help_text="密钥仅保存在服务端，不会返回给浏览器",
        ),
        CredentialField(
            key="ai_base_url",
            label="接口地址（Base URL）",
            secret=False,
            placeholder="https://api.deepseek.com/v1",
            help_text="需包含版本路径，例如 /v1 或 /v4",
        ),
        CredentialField(
            key="ai_model",
            label="模型名称",
            secret=False,
            placeholder="deepseek-chat",
        ),
    )

    def __init__(
        self,
        name: str,
        label: str,
        description: str,
        default_base_url: str,
        models: tuple[str, ...],
    ) -> None:
        self.name = name
        self.label = label
        self.description = description
        self.default_base_url = default_base_url
        self.models = models

    def available(self, settings: dict) -> tuple[bool, str]:
        if not settings.get("ai_api_key"):
            return False, "未配置 AI API Key"
        base_url = str(settings.get("ai_base_url") or self.default_base_url or "").strip()
        if not base_url.startswith(("http://", "https://")):
            return False, "接口地址无效，需要以 http(s):// 开头"
        return True, "凭据已配置"

    def _endpoint(self, settings: dict) -> str:
        base_url = str(settings.get("ai_base_url") or self.default_base_url or "").strip().rstrip("/")
        if not base_url:
            raise ProviderError("未配置接口地址", code="config")
        return f"{base_url}/chat/completions"

    def chat(
        self,
        messages: list[ChatMessage],
        settings: dict,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AIResult:
        api_key = str(settings.get("ai_api_key") or "")
        if not api_key:
            raise ProviderError("缺少 AI API Key，请在设置中配置", code="auth")

        chosen_model = model or str(settings.get("ai_model") or (self.models[0] if self.models else ""))
        if not chosen_model:
            raise ProviderError("未指定模型名称", code="config")

        payload = {
            "model": chosen_model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": float(
                temperature if temperature is not None else settings.get("ai_temperature", 0.3)
            ),
            "max_tokens": int(max_tokens if max_tokens is not None else settings.get("ai_max_tokens", 2048)),
            "stream": False,
        }

        started = time.perf_counter()
        response = request_json(
            "POST",
            self._endpoint(settings),
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=(10, int(settings.get("request_timeout", 45))),
            retries=1,
        )
        elapsed = (time.perf_counter() - started) * 1000

        if isinstance(response.get("error"), dict):
            message = response["error"].get("message") or "未知错误"
            raise ProviderError(f"模型返回错误：{message}", code="upstream")

        choices = response.get("choices") or []
        if not choices:
            raise ProviderError("模型未返回任何结果", code="empty_result")

        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            # 部分兼容实现返回分段内容
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("模型返回内容为空", code="empty_result")

        usage = response.get("usage") or {}
        return AIResult(
            text=content.strip(),
            provider=self.name,
            model=chosen_model,
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
            latency_ms=round(elapsed, 1),
            meta={
                "demo": False,
                "finish_reason": choices[0].get("finish_reason"),
                "total_tokens": usage.get("total_tokens"),
            },
        )


#: 预置平台。base_url 可在设置页覆盖，便于使用代理或私有部署。
PRESETS: tuple[OpenAICompatibleProvider, ...] = (
    OpenAICompatibleProvider(
        name="deepseek",
        label="DeepSeek",
        description="DeepSeek 开放平台，中文能力强，价格低，推荐作为默认云端引擎。",
        default_base_url="https://api.deepseek.com/v1",
        models=("deepseek-chat", "deepseek-reasoner"),
    ),
    OpenAICompatibleProvider(
        name="kimi",
        label="Kimi（Moonshot）",
        description="Moonshot AI 开放平台，长上下文能力突出。",
        default_base_url="https://api.moonshot.cn/v1",
        models=("moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"),
    ),
    OpenAICompatibleProvider(
        name="zhipu",
        label="智谱 GLM",
        description="智谱开放平台，GLM-4 系列模型，支持 OpenAI 兼容接口。",
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
        models=("glm-4-flash", "glm-4-air", "glm-4-plus"),
    ),
    OpenAICompatibleProvider(
        name="qwen",
        label="通义千问",
        description="阿里云百炼兼容模式，通义千问系列模型。",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=("qwen-plus", "qwen-turbo", "qwen-max"),
    ),
    OpenAICompatibleProvider(
        name="custom",
        label="自定义（OpenAI 兼容）",
        description="任何兼容 /chat/completions 的服务，如 Ollama、vLLM、OneAPI。",
        default_base_url="",
        models=(),
    ),
)


def build_presets() -> list[OpenAICompatibleProvider]:
    return list(PRESETS)
