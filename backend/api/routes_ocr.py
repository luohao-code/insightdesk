"""OCR 相关接口：引擎列表、图片上传、单图识别。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..providers import ProviderError
from ..schemas import RecognizeRequest, UploadResponse, UploadedImage
from ..services import image_service, ocr_service, serializers, settings_service
from ..services.image_service import UploadError
from ..utils.security import SecurityError

router = APIRouter(prefix="/ocr", tags=["OCR"])
logger = logging.getLogger(__name__)


@router.get("/engines", summary="获取 OCR 引擎列表")
def engines(db: Session = Depends(get_db)) -> dict:
    settings = settings_service.get_all(db)
    from ..providers import ocr_catalog

    catalog = ocr_catalog(settings)
    return {
        "items": catalog,
        "default": settings.get("ocr_engine"),
        "available": [item["name"] for item in catalog if item["available"]],
    }


@router.post("/upload", response_model=UploadResponse, summary="上传图片（支持多张）")
async def upload(files: list[UploadFile] = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="请选择至少一张图片")
    if len(files) > 100:
        raise HTTPException(status_code=400, detail="单次最多上传 100 张图片")

    settings = settings_service.get_all(db)
    max_mb = int(settings.get("max_file_mb") or 20)
    accepted: list[UploadedImage] = []
    rejected: list[dict] = []

    for upload_file in files:
        filename = upload_file.filename or "image"
        try:
            data = await upload_file.read()
            if len(data) > max_mb * 1024 * 1024:
                raise UploadError(f"文件超过 {max_mb}MB 上限")
            info = image_service.save_bytes(data, filename, max_mb=max_mb)
            payload = image_service.to_public(info["id"], filename, info)
            accepted.append(UploadedImage(**payload))
        except (UploadError, SecurityError) as exc:
            rejected.append({"filename": filename, "reason": str(exc)})
        except Exception as exc:  # pragma: no cover - 兜底
            logger.exception("上传失败：%s", filename)
            rejected.append({"filename": filename, "reason": f"上传失败：{exc}"})
        finally:
            await upload_file.close()

    if not accepted and rejected:
        raise HTTPException(status_code=400, detail="；".join(item["reason"] for item in rejected[:3]))

    return UploadResponse(images=accepted, rejected=rejected)


@router.post("/recognize", summary="识别单张图片")
def recognize(payload: RecognizeRequest, db: Session = Depends(get_db)) -> dict:
    settings = settings_service.get_all(db)
    options = {
        "engine": payload.engine,
        "language": payload.language,
        "grayscale": payload.grayscale,
        "autocontrast": payload.autocontrast,
        "rotate": payload.rotate,
        "max_long_edge": payload.max_long_edge,
        "merge_lines": payload.merge_lines,
        "save": payload.save,
    }
    try:
        result, document, provider, note = ocr_service.recognize_image_id(
            db, payload.image_id, settings, request_options=options
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except UploadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    demo = bool(result.meta.get("demo"))
    return {
        "document_id": document.id if document else None,
        "text": result.text,
        "blocks": [
            {
                "text": block.text,
                "confidence": block.confidence,
                "box": block.box,
            }
            for block in result.blocks
        ],
        "engine": provider.name,
        "engine_label": provider.label,
        "confidence": round(float(result.confidence or 0.0), 3),
        "duration_ms": round(float(result.duration_ms or 0.0), 1),
        "char_count": document.char_count if document else len(result.text),
        "language": payload.language,
        "demo": demo,
        "notice": result.meta.get("notice") or note,
        "image_url": serializers.upload_url(payload.image_id) if payload.image_id else None,
        "thumbnail_url": serializers.upload_thumb_url(payload.image_id) if payload.image_id else None,
    }
