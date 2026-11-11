"""导出接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import export_service
from ..services.export_service import ExportError

router = APIRouter(prefix="/export", tags=["导出"])


class ExportRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    format: str = "txt"


@router.get("/formats", summary="支持的导出格式")
def formats() -> dict:
    return {
        "items": [
            {"format": key, "label": label}
            for key, label in export_service.SUPPORTED_FORMATS.items()
        ]
    }


@router.post("", summary="导出记录")
def export(payload: ExportRequest, db: Session = Depends(get_db)):
    try:
        result = export_service.export(db, payload.ids, payload.format)
    except ExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": export_service.content_disposition(result.filename),
            "X-Export-Count": str(result.count),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Export-Count",
        },
    )
