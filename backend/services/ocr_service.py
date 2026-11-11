"""OCR 业务服务。

负责：引擎选择与降级、图像预处理、结果后处理、落库。
具体的网络调用与本地推理由 ``providers.ocr`` 中的引擎完成。
"""

from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy.orm import Session

from .. import config
from ..models import Document
from ..providers import OCRProvider, OCRResult, ProviderError, get_ocr, ocr_providers
from ..utils.files import ensure_dir, remove_quiet, relative_path
from ..utils.images import ImageError, make_thumbnail, preprocess_image
from ..utils.text import clean_text, count_chars, detect_language, merge_soft_wraps
from ..utils.time import now_iso

_PREPARE_DIR = config.UPLOAD_DIR / "prepared"


def resolve_engine(settings: dict, requested: str | None = None) -> tuple[OCRProvider, str | None]:
    """选择 OCR 引擎。

    优先级：显式请求 → 设置中的默认引擎。
    若首选引擎不可用，自动降级到演示引擎，并返回降级说明。
    """

    candidates: list[str] = []
    if requested:
        candidates.append(requested)
    default = str(settings.get("ocr_engine") or config.MOCK_OCR_ENGINE)
    if default not in candidates:
        candidates.append(default)
    if config.MOCK_OCR_ENGINE not in candidates:
        candidates.append(config.MOCK_OCR_ENGINE)

    reasons: list[str] = []
    for name in candidates:
        try:
            provider = get_ocr(name)
        except KeyError:
            reasons.append(f"{name} 不存在")
            continue
        available, reason = provider.available(settings)
        if available:
            note = None
            if requested and name != requested:
                note = f"请求的引擎 {requested} 不可用，已自动使用 {provider.label}"
            elif name != default:
                note = f"默认引擎不可用（{'; '.join(reasons)}），已使用 {provider.label}"
            return provider, note
        reasons.append(f"{provider.label}：{reason}")

    raise ProviderError("没有可用的 OCR 引擎：" + "；".join(reasons), code="no_engine")


def list_available(settings: dict) -> list[dict]:
    items = []
    for provider in ocr_providers().values():
        available, reason = provider.available(settings)
        items.append(
            {
                "name": provider.name,
                "label": provider.label,
                "available": available,
                "reason": reason,
            }
        )
    return items


def _prepare(image_path: Path, image_id: str, options: dict) -> tuple[Path, Path | None]:
    """按需生成预处理图片，返回 ``(待识别路径, 临时文件路径)``。"""

    needs_preprocess = any(
        [
            options.get("grayscale"),
            options.get("autocontrast"),
            float(options.get("rotate") or 0) != 0,
            int(options.get("max_long_edge") or 0) not in (0, 2400),
        ]
    )
    if not needs_preprocess:
        return image_path, None

    ensure_dir(_PREPARE_DIR)
    target = _PREPARE_DIR / f"{image_id}_{int(time.time() * 1000)}.png"
    try:
        preprocess_image(
            image_path,
            target,
            grayscale=bool(options.get("grayscale")),
            autocontrast=bool(options.get("autocontrast")),
            max_long_edge=int(options.get("max_long_edge") or 2400),
            rotate_degrees=float(options.get("rotate") or 0),
        )
        return target, target
    except (ImageError, OSError):
        return image_path, None


def recognize_file(
    db: Session,
    *,
    image_path: Path,
    filename: str,
    settings: dict,
    engine: str | None = None,
    options: dict | None = None,
    image_id: str | None = None,
    source_type: str = "image",
    source_url: str | None = None,
    title: str | None = None,
    save: bool = True,
) -> tuple[OCRResult, Document | None, OCRProvider, str | None]:
    """识别单张图片并按需保存为文字资产。

    :returns: ``(识别结果, 文档或 None, 引擎实例, 降级说明)``
    """

    options = options or {}
    provider, note = resolve_engine(settings, engine)
    image_id = image_id or image_path.stem

    prepared_path, temporary = _prepare(image_path, image_id, options)
    try:
        result = provider.recognize(prepared_path, settings, options)
    finally:
        remove_quiet(temporary)

    text = clean_text(result.text)
    if options.get("merge_lines", True):
        text = merge_soft_wraps(text)
    if not text:
        raise ProviderError("识别结果为空，请更换清晰度更高的图片", code="empty_result")

    result.text = text
    result.engine = provider.name
    result.meta = {**(result.meta or {}), "engine_label": provider.label}
    if note:
        result.meta["fallback_note"] = note

    document: Document | None = None
    if save:
        thumb_relative = None
        thumb_file = config.THUMB_DIR / f"{image_id}.png"
        if not thumb_file.exists():
            try:
                make_thumbnail(image_path, thumb_file)
            except Exception:
                thumb_file = None
        if thumb_file and thumb_file.exists():
            thumb_relative = relative_path(thumb_file)

        document = Document(
            title=(title or Path(filename).stem or "未命名文档")[:255],
            filename=filename[:255],
            source_type=source_type,
            source_url=source_url,
            content=text,
            original_content=text,
            engine=provider.name,
            language=str(options.get("language") or settings.get("ocr_language") or "auto"),
            confidence=float(result.confidence or 0.0),
            char_count=count_chars(text),
            status="ok",
            image_path=relative_path(image_path),
            thumb_path=thumb_relative,
            tags="[]",
        )
        document.meta_dict = {
            "demo": bool(result.meta.get("demo")),
            "engine_label": provider.label,
            "duration_ms": result.duration_ms,
            "detected_language": detect_language(text),
        }
        db.add(document)
        db.commit()
        db.refresh(document)

    return result, document, provider, note


def recognize_image_id(
    db: Session,
    image_id: str,
    settings: dict,
    *,
    request_options: dict | None = None,
) -> tuple[OCRResult, Document | None, OCRProvider, str | None]:
    """按上传图片 ID 识别（供单图接口调用）。"""

    from . import image_service

    path = image_service.get_path(image_id)
    options = dict(request_options or {})
    filename = options.pop("filename", path.name)
    return recognize_file(
        db,
        image_path=path,
        filename=filename,
        settings=settings,
        engine=options.pop("engine", None),
        options=options,
        image_id=image_id,
        save=bool(options.pop("save", True)),
    )


def health(settings: dict) -> dict:
    """引擎健康状态，供 ``/api/health`` 使用。"""

    engines = list_available(settings)
    return {
        "available": [item["name"] for item in engines if item["available"]],
        "unavailable": [item["name"] for item in engines if not item["available"]],
        "total": len(engines),
        "generated_at": now_iso(),
    }
