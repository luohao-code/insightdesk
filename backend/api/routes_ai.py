"""AI 能力接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..providers import ProviderError
from ..schemas import AIProcessRequest, ChatRequest
from ..services import ai_service, settings_service
from ..services.ai_service import AIServiceError

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/actions", summary="AI 动作列表")
def actions() -> dict:
    return {"items": ai_service.actions()}


@router.get("/providers", summary="AI 引擎列表")
def providers(db: Session = Depends(get_db)) -> dict:
    settings = settings_service.get_all(db)
    return {
        "items": ai_service.catalog(settings),
        "default": settings.get("ai_provider"),
        "default_model": settings.get("ai_model"),
    }


@router.post("/process", summary="执行 AI 处理（翻译/摘要/关键词/问答/润色/提纲）")
def process(payload: AIProcessRequest, db: Session = Depends(get_db)) -> dict:
    settings = settings_service.get_all(db)
    try:
        return ai_service.process(
            db,
            settings,
            action=payload.action,
            document_id=payload.document_id,
            text=payload.text,
            provider=payload.provider,
            model=payload.model,
            options=payload.options,
            save=payload.save,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/chat", summary="多轮问答")
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> dict:
    settings = settings_service.get_all(db)
    try:
        return ai_service.chat(
            db,
            settings,
            message=payload.message,
            conversation_id=payload.conversation_id,
            document_id=payload.document_id,
            provider=payload.provider,
            model=payload.model,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/conversations", summary="会话列表")
def conversations(db: Session = Depends(get_db)) -> dict:
    items = ai_service.list_conversations(db)
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "document_id": item.document_id,
                "updated_at": item.updated_at,
                "message_count": len(item.messages),
            }
            for item in items
        ]
    }


@router.get("/conversations/{conversation_id}", summary="会话详情")
def conversation_detail(conversation_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        conversation = ai_service.get_conversation(db, conversation_id)
    except AIServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ai_service.conversation_out(conversation)


@router.delete("/conversations/{conversation_id}", summary="删除会话")
def conversation_delete(conversation_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        ai_service.delete_conversation(db, conversation_id)
    except AIServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}
