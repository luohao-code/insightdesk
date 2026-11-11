"""设置与引擎连通性测试接口。"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from ..db import get_db
from ..providers import ChatMessage, ProviderError, get_ai, get_ocr
from ..schemas import ProviderTestRequest, SettingsUpdate
from ..services import settings_service
from ..services.settings_service import SettingsError

router = APIRouter(prefix="/settings", tags=["设置"])


@router.get("", summary="读取设置（密钥脱敏）")
def read_settings(db: Session = Depends(get_db)) -> dict:
    return settings_service.masked_view(db)


@router.put("", summary="更新设置")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        settings_service.update(db, payload.values)
    except SettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return settings_service.masked_view(db)


@router.post("/test", summary="测试引擎连通性")
def test_provider(payload: ProviderTestRequest, db: Session = Depends(get_db)) -> dict:
    settings = settings_service.get_all(db)
    started = time.perf_counter()

    if payload.kind == "ocr":
        try:
            provider = get_ocr(payload.name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"未知的 OCR 引擎：{payload.name}") from exc
        available, reason = provider.available(settings)
        if not available:
            return {"ok": False, "name": provider.name, "label": provider.label, "message": reason}
        sample = _sample_image()
        try:
            result = provider.recognize(sample, settings, {"language": "en", "merge_lines": True})
        except ProviderError as exc:
            return {
                "ok": False,
                "name": provider.name,
                "label": provider.label,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "message": str(exc),
            }
        finally:
            sample.unlink(missing_ok=True)
        return {
            "ok": True,
            "name": provider.name,
            "label": provider.label,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "message": f"测试通过，识别预览：{result.text[:60]}",
        }

    try:
        provider = get_ai(payload.name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"未知的 AI 引擎：{payload.name}") from exc

    available, reason = provider.available(settings)
    if not available:
        return {"ok": False, "name": provider.name, "label": provider.label, "message": reason}

    try:
        result = provider.chat(
            [ChatMessage(role="user", content="请只回复两个字符：OK")],
            settings,
            max_tokens=16,
            temperature=0,
        )
    except ProviderError as exc:
        return {
            "ok": False,
            "name": provider.name,
            "label": provider.label,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "message": str(exc),
        }

    return {
        "ok": True,
        "name": provider.name,
        "label": provider.label,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "message": f"测试通过，模型回复：{result.text[:60]}",
    }


def _sample_image() -> Path:
    """生成一张用于引擎自检的图片（不写入用户数据目录）。"""

    image = Image.new("RGB", (720, 220), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=44)
    except TypeError:  # 旧版 Pillow
        font = ImageFont.load_default()
    draw.text((32, 80), "InsightDesk OCR Test 2026", fill="black", font=font)
    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    handle.close()
    path = Path(handle.name)
    image.save(path, format="PNG")
    return path
