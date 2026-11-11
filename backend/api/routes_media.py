"""媒体文件访问接口。

只暴露数据目录内的受管文件，路径全部通过数据库记录或严格的 ID 校验获得，
不接受用户直接传入文件路径。
"""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Document, Task
from ..services import image_service
from ..utils.files import abs_path

router = APIRouter(prefix="/media", tags=["媒体"])


def _file_response(path, filename: str | None = None) -> FileResponse:
    if path is None or not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在或已被清理")
    media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    headers = {"Cache-Control": "private, max-age=3600"}
    return FileResponse(path, media_type=media_type, filename=filename, headers=headers)


@router.get("/upload/{image_id}", summary="读取上传原图")
def upload_image(image_id: str):
    try:
        path = image_service.get_path(image_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _file_response(path)


@router.get("/upload/{image_id}/thumb", summary="读取上传缩略图")
def upload_thumb(image_id: str):
    path = image_service.get_thumb(image_id)
    if path is None:
        raise HTTPException(status_code=404, detail="缩略图不存在")
    return _file_response(path)


@router.get("/document/{document_id}/image", summary="读取记录原图")
def document_image(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _file_response(abs_path(document.image_path))


@router.get("/document/{document_id}/thumb", summary="读取记录缩略图")
def document_thumb(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _file_response(abs_path(document.thumb_path))


@router.get("/task/{task_id}/image", summary="读取任务原图")
def task_image(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _file_response(abs_path(task.image_path))


@router.get("/task/{task_id}/thumb", summary="读取任务缩略图")
def task_thumb(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.image_path:
        raise HTTPException(status_code=404, detail="缩略图不存在")
    image_id = task.image_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    path = image_service.get_thumb(image_id)
    if path is None:
        raise HTTPException(status_code=404, detail="缩略图不存在")
    return _file_response(path)
