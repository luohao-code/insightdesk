"""AI 业务服务。

统一调度翻译、摘要、关键词、问答等动作，记录调用明细，
并保证 AI 结果不会直接覆盖用户原文。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import AIRun, Conversation, Document, Message
from ..prompts import build_prompt, get_spec, list_actions
from ..providers import AIProvider, ProviderError, ai_providers, get_ai
from ..utils.text import truncate
from ..utils.time import now_iso


class AIServiceError(ValueError):
    """AI 请求参数或上下文错误。"""


def resolve_provider(settings: dict, requested: str | None = None) -> tuple[AIProvider, str | None]:
    """选择 AI 引擎，不可用时降级到演示引擎。"""

    candidates: list[str] = []
    if requested:
        candidates.append(requested)
    default = str(settings.get("ai_provider") or config.MOCK_AI_PROVIDER)
    if default not in candidates:
        candidates.append(default)
    if config.MOCK_AI_PROVIDER not in candidates:
        candidates.append(config.MOCK_AI_PROVIDER)

    reasons: list[str] = []
    for name in candidates:
        try:
            provider = get_ai(name)
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

    raise ProviderError("没有可用的 AI 引擎：" + "；".join(reasons), code="no_engine")


def _document_text(db: Session, document_id: int | None) -> Document | None:
    if document_id is None:
        return None
    document = db.get(Document, document_id)
    if document is None:
        raise AIServiceError("指定的文档不存在")
    return document


def process(
    db: Session,
    settings: dict,
    *,
    action: str,
    document_id: int | None = None,
    text: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    options: dict | None = None,
    save: bool = True,
) -> dict:
    """执行一次 AI 处理并返回结构化结果。"""

    try:
        spec = get_spec(action)
    except KeyError as exc:
        raise AIServiceError(str(exc)) from exc

    document = _document_text(db, document_id)
    source = (text or (document.content if document else "") or "").strip()
    if not source:
        raise AIServiceError("没有可处理的文本，请先识别图片或粘贴内容")

    options = options or {}
    ai_provider, note = resolve_provider(settings, provider)
    bundle = build_prompt(action, source, options)
    chosen_model = model or str(settings.get("ai_model") or "")

    result = ai_provider.process(
        action,
        source,
        bundle.system,
        bundle.user,
        settings,
        model=chosen_model or None,
        options=options,
    )

    run_id = None
    if save:
        run = AIRun(
            document_id=document.id if document else None,
            action=action,
            provider=ai_provider.name,
            model=result.model,
            input_text=truncate(source, 4000, suffix="…"),
            output_text=result.text,
            prompt=truncate(bundle.rendered, 6000, suffix="…"),
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            latency_ms=result.latency_ms,
            status="ok",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    notice = result.meta.get("notice") or note
    return {
        "run_id": run_id,
        "action": spec.action,
        "output": result.text,
        "provider": ai_provider.name,
        "provider_label": ai_provider.label,
        "model": result.model,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "latency_ms": result.latency_ms,
        "demo": bool(result.meta.get("demo")),
        "notice": notice,
        "truncated": bundle.truncated,
        "document_id": document.id if document else None,
    }


def chat(
    db: Session,
    settings: dict,
    *,
    message: str,
    conversation_id: int | None = None,
    document_id: int | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """多轮问答。"""

    content = (message or "").strip()
    if not content:
        raise AIServiceError("问题不能为空")

    ai_provider, note = resolve_provider(settings, provider)
    conversation: Conversation | None = None
    if conversation_id is not None:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            raise AIServiceError("会话不存在")
    else:
        conversation = Conversation(
            title=truncate(content, 30),
            document_id=document_id,
            provider=ai_provider.name,
            model=model or "",
        )
        db.add(conversation)
        db.flush()

    context_document = _document_text(db, document_id or conversation.document_id)
    if context_document and not conversation.document_id:
        conversation.document_id = context_document.id

    user_message = Message(conversation_id=conversation.id, role="user", content=content)
    db.add(user_message)
    db.flush()

    history = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id.desc())
            .limit(12)
        ).all()
    )
    history.reverse()

    from ..providers import ChatMessage

    payload: list[ChatMessage] = []
    if context_document:
        payload.append(
            ChatMessage(
                role="system",
                content=(
                    "你是一位阅读助手。请仅依据以下原文回答用户问题，"
                    "无法从原文得出答案时要明确说明。\n\n原文：\n"
                    + truncate(context_document.content, 10000, suffix="…")
                ),
            )
        )
    for item in history:
        payload.append(ChatMessage(role=item.role, content=item.content))

    result = ai_provider.chat(
        payload,
        settings,
        model=model or str(settings.get("ai_model") or "") or None,
    )

    assistant = Message(conversation_id=conversation.id, role="assistant", content=result.text)
    db.add(assistant)
    conversation.updated_at = now_iso()
    if conversation.title in {"新的对话", ""}:
        conversation.title = truncate(content, 30)
    db.commit()
    db.refresh(conversation)
    db.refresh(assistant)

    notice = result.meta.get("notice") or note
    return {
        "conversation": conversation_out(conversation),
        "reply": {
            "id": assistant.id,
            "role": assistant.role,
            "content": assistant.content,
            "created_at": assistant.created_at,
        },
        "provider": ai_provider.name,
        "model": result.model,
        "demo": bool(result.meta.get("demo")),
        "latency_ms": result.latency_ms,
        "notice": notice,
    }


def conversation_out(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "document_id": conversation.document_id,
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
            }
            for message in conversation.messages
        ],
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


def list_conversations(db: Session, limit: int = 30) -> list[Conversation]:
    return list(
        db.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(limit)).all()
    )


def get_conversation(db: Session, conversation_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise AIServiceError("会话不存在")
    return conversation


def delete_conversation(db: Session, conversation_id: int) -> None:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise AIServiceError("会话不存在")
    db.delete(conversation)
    db.commit()


def catalog(settings: dict) -> list[dict]:
    items = []
    for provider in ai_providers().values():
        available, reason = provider.available(settings)
        items.append(
            {
                "name": provider.name,
                "label": provider.label,
                "description": provider.description,
                "requires_credentials": provider.requires_credentials,
                "available": available,
                "reason": reason,
                "default_base_url": provider.default_base_url,
                "models": list(provider.models),
                "credential_fields": [
                    {
                        "key": field.key,
                        "label": field.label,
                        "secret": field.secret,
                        "placeholder": field.placeholder,
                        "help_text": field.help_text,
                    }
                    for field in provider.credential_fields
                ],
            }
        )
    return items


def actions() -> list[dict]:
    return list_actions()
