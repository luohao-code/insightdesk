"""RapidOCR 本地离线引擎适配。

RapidOCR 基于 ONNXRuntime，安装后即可离线识别中英文印刷体，
无需任何云端密钥。依赖为可选安装：

    pip install rapidocr-onnxruntime
"""

from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path

from ..base import OCRProvider, OCRResult, ProviderError, TextBlock

_ENGINE_LOCK = threading.Lock()
_ENGINE = None
_ENGINE_ERROR: str | None = None


class RapidOCRProvider(OCRProvider):
    name = "rapidocr"
    label = "RapidOCR（本地离线）"
    description = "基于 ONNXRuntime 的本地 OCR，无需联网与密钥，首次加载模型略慢。"
    requires_credentials = False
    supports_language = ("auto", "zh", "en")

    def available(self, settings: dict) -> tuple[bool, str]:
        if importlib.util.find_spec("rapidocr_onnxruntime") is None:
            return False, "未安装 rapidocr-onnxruntime，可执行 pip install rapidocr-onnxruntime 后启用"
        if _ENGINE_ERROR:
            return False, f"引擎初始化失败：{_ENGINE_ERROR}"
        return True, "本地引擎可用"

    def _engine(self):
        global _ENGINE, _ENGINE_ERROR
        if _ENGINE is not None:
            return _ENGINE
        with _ENGINE_LOCK:
            if _ENGINE is not None:
                return _ENGINE
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore

                _ENGINE = RapidOCR()
                return _ENGINE
            except Exception as exc:  # pragma: no cover - 依赖本地环境
                _ENGINE_ERROR = str(exc)
                raise ProviderError(f"RapidOCR 初始化失败：{exc}", code="engine_init") from exc

    def recognize(self, image_path: Path, settings: dict, options: dict | None = None) -> OCRResult:
        started = time.perf_counter()
        engine = self._engine()
        try:
            result, _elapse = engine(str(image_path))
        except Exception as exc:  # pragma: no cover - 依赖本地环境
            raise ProviderError(f"本地识别失败：{exc}", code="engine_error", retryable=True) from exc

        if not result:
            raise ProviderError("未在图片中检测到文字", code="empty_result")

        blocks: list[TextBlock] = []
        for item in result:
            try:
                box, text, score = item[0], item[1], item[2]
            except (TypeError, IndexError):
                continue
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=str(text),
                    confidence=float(score) if score is not None else None,
                    box=[[float(point[0]), float(point[1])] for point in box] if box else None,
                )
            )

        if not blocks:
            raise ProviderError("识别结果为空", code="empty_result")

        duration = (time.perf_counter() - started) * 1000
        confidences = [block.confidence for block in blocks if block.confidence is not None]
        return OCRResult(
            text="\n".join(block.text for block in blocks),
            blocks=blocks,
            engine=self.name,
            confidence=round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
            duration_ms=round(duration, 1),
            meta={"demo": False, "language": options_language(options)},
        )


def options_language(options: dict | None) -> str:
    return (options or {}).get("language", "auto")


provider = RapidOCRProvider()
