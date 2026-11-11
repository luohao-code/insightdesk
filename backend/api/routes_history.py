"""历史记录接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import BulkDeleteRequest, DocumentPatch
from ..services import history_service, serializers
from ..services.history_service import HistoryError

router = APIRouter(prefix="/history", tags=["历史记录"])


@router.get("", summary="查询历史记录")
def list_documents(
    q: str | None = None,
    source_type: str | None = None,
    engine: str | None = None,
    favorite: bool | None = None,
    tag: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = Query("updated_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return history_service.list_documents(
        db,
        query=q,
        source_type=source_type,
        engine=engine,
        favorite=favorite,
        tag=tag,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/tags", summary="标签统计")
def tags(db: Session = Depends(get_db)) -> dict:
    return {"items": history_service.all_tags(db)}


@router.get("/stats", summary="历史记录统计")
def stats(db: Session = Depends(get_db)) -> dict:
    return history_service.stats(db)


@router.post("/bulk-delete", summary="批量删除")
def bulk_delete(payload: BulkDeleteRequest, db: Session = Depends(get_db)) -> dict:
    deleted = history_service.bulk_delete(db, payload.ids)
    return {"ok": True, "deleted": deleted}


@router.get("/{document_id}", summary="记录详情")
def get_document(document_id: int, db: Session = Depends(get_db)):
    try:
        document = history_service.get_document(db, document_id)
    except HistoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serializers.document_out(document, full=True)


@router.patch("/{document_id}", summary="更新记录（编辑文本/标签/收藏）")
def update_document(document_id: int, payload: DocumentPatch, db: Session = Depends(get_db)):
    try:
        document = history_service.update_document(
            db,
            document_id,
            title=payload.title,
            content=payload.content,
            tags=payload.tags,
            favorite=payload.favorite,
        )
    except HistoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serializers.document_out(document, full=True)


@router.delete("/{document_id}", summary="删除记录")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    try:
        history_service.delete_document(db, document_id)
    except HistoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}
