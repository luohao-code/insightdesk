"""统计看板接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import stats_service

router = APIRouter(prefix="/stats", tags=["统计"])


@router.get("/overview", summary="看板总览")
def overview(db: Session = Depends(get_db)) -> dict:
    return stats_service.overview(db)
