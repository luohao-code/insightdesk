"""网页提取与自动打开接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import WebExtractRequest, WebOpenRequest
from ..services import settings_service, web_extract_service
from ..services.web_extract_service import WebExtractError

router = APIRouter(prefix="/web", tags=["网页提取"])


@router.post("/extract", summary="提取网页正文")
def extract(payload: WebExtractRequest, db: Session = Depends(get_db)) -> dict:
    settings = settings_service.get_all(db)
    try:
        return web_extract_service.extract(
            db,
            settings,
            payload.url,
            save=payload.save,
            to_document=payload.to_document,
            auto_open=payload.auto_open,
        )
    except WebExtractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/open", summary="调用系统浏览器打开网页")
def open_url(payload: WebOpenRequest) -> dict:
    try:
        return web_extract_service.open_url(payload.url)
    except WebExtractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history", summary="网页提取历史")
def history(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> dict:
    records = web_extract_service.recent(db, limit=limit)
    return {"items": [web_extract_service.record_out(item) for item in records]}


@router.get("/records/{record_id}", summary="网页提取详情")
def record_detail(record_id: int, db: Session = Depends(get_db)) -> dict:
    from ..models import WebExtraction

    record = db.get(WebExtraction, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="网页提取记录不存在")
    return web_extract_service.record_out(record)


@router.post("/records/{record_id}/to-document", summary="把网页提取结果转为文字资产")
def to_document(record_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        document = web_extract_service.record_to_document(db, record_id)
    except WebExtractError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from ..services.serializers import document_out

    return {"ok": True, "document": document_out(document)}
