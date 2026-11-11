"""历史记录服务。

检索策略：
* 查询长度 ≥ 3 且 FTS 可用时，使用 trigram 索引进行子串匹配；
* 其它情况使用 ``LIKE`` 扫描（在万级数据量下仍可接受）；
* 两种方式都支持来源、引擎、收藏、标签与时间范围筛选。
"""

from __future__ import annotations

import time

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from ..db import fts_available
from ..models import Document
from ..utils.files import abs_path, remove_quiet
from ..utils.text import count_chars, truncate
from ..utils.time import now_iso
from . import serializers


class HistoryError(ValueError):
    """历史记录操作失败。"""


def _fts_ids(db: Session, query: str) -> list[int] | None:
    if not fts_available():
        return None
    term = query.strip()
    if len(term) < 3:
        return None
    match = '"' + term.replace('"', '""') + '"'
    try:
        rows = db.execute(
            text("SELECT rowid FROM documents_fts WHERE documents_fts MATCH :match"),
            {"match": match},
        ).scalars().all()
        return [int(row) for row in rows]
    except Exception:
        return None


def list_documents(
    db: Session,
    *,
    query: str | None = None,
    source_type: str | None = None,
    engine: str | None = None,
    favorite: bool | None = None,
    tag: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "updated_desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    started = time.perf_counter()
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))

    statement = select(Document)
    counter = select(func.count(Document.id))
    conditions = []

    if query and query.strip():
        ids = _fts_ids(db, query)
        if ids is not None:
            if not ids:
                return {
                    "items": [], "total": 0, "page": page, "page_size": page_size,
                    "pages": 0, "took_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            conditions.append(Document.id.in_(ids))
        else:
            like = f"%{query.strip()}%"
            conditions.append(
                or_(Document.title.like(like), Document.content.like(like), Document.tags.like(like))
            )

    if source_type:
        conditions.append(Document.source_type == source_type)
    if engine:
        conditions.append(Document.engine == engine)
    if favorite is not None:
        conditions.append(Document.favorite == bool(favorite))
    if tag:
        conditions.append(Document.tags.like(f'%"{tag}"%'))
    if date_from:
        conditions.append(Document.created_at >= date_from)
    if date_to:
        conditions.append(Document.created_at <= date_to)

    for condition in conditions:
        statement = statement.where(condition)
        counter = counter.where(condition)

    sort_map = {
        "updated_desc": Document.updated_at.desc(),
        "created_desc": Document.created_at.desc(),
        "created_asc": Document.created_at.asc(),
        "chars_desc": Document.char_count.desc(),
        "title_asc": Document.title.asc(),
    }
    statement = statement.order_by(sort_map.get(sort, Document.updated_at.desc()))

    total = db.scalar(counter) or 0
    items = list(db.scalars(statement.limit(page_size).offset((page - 1) * page_size)).all())
    pages = (total + page_size - 1) // page_size

    return {
        "items": [serializers.document_out(item, full=False) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "took_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def get_document(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HistoryError("记录不存在")
    return document


def update_document(
    db: Session,
    document_id: int,
    *,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    favorite: bool | None = None,
) -> Document:
    document = get_document(db, document_id)

    if title is not None:
        document.title = title.strip()[:255] or document.title
    if content is not None and content != document.content:
        document.content = content
        document.char_count = count_chars(content)
        document.version += 1
    if tags is not None:
        cleaned = []
        for tag in tags[:20]:
            value = str(tag).strip()[:24]
            if value and value not in cleaned:
                cleaned.append(value)
        document.tags_list = cleaned
    if favorite is not None:
        document.favorite = bool(favorite)

    document.updated_at = now_iso()
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document_id: int) -> None:
    document = get_document(db, document_id)
    remove_quiet(abs_path(document.image_path))
    remove_quiet(abs_path(document.thumb_path))
    db.delete(document)
    db.commit()


def bulk_delete(db: Session, ids: list[int]) -> int:
    documents = list(db.scalars(select(Document).where(Document.id.in_(ids))).all())
    for document in documents:
        remove_quiet(abs_path(document.image_path))
        remove_quiet(abs_path(document.thumb_path))
        db.delete(document)
    db.commit()
    return len(documents)


def stats(db: Session) -> dict:
    total = db.scalar(select(func.count(Document.id))) or 0
    favorites = db.scalar(select(func.count(Document.id)).where(Document.favorite.is_(True))) or 0
    total_chars = db.scalar(select(func.sum(Document.char_count))) or 0
    engines = {
        str(engine or "unknown"): int(count)
        for engine, count in db.execute(
            select(Document.engine, func.count(Document.id)).group_by(Document.engine)
        ).all()
    }
    return {
        "total": total,
        "favorites": favorites,
        "total_chars": int(total_chars),
        "engines": engines,
    }


def all_tags(db: Session, limit: int = 50) -> list[dict]:
    """统计标签使用频次，供筛选器展示。"""

    counter: dict[str, int] = {}
    for (raw,) in db.execute(select(Document.tags)).all():
        try:
            import json

            values = json.loads(raw or "[]")
        except ValueError:
            continue
        if not isinstance(values, list):
            continue
        for value in values:
            key = str(value)
            counter[key] = counter.get(key, 0) + 1
    ordered = sorted(counter.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [{"tag": tag, "count": count} for tag, count in ordered]


def recent(db: Session, limit: int = 6) -> list[dict]:
    items = list(db.scalars(select(Document).order_by(Document.created_at.desc()).limit(limit)).all())
    return [serializers.document_out(item, full=False) for item in items]


def excerpt(content: str | None, limit: int = 140) -> str:
    return truncate(content, limit)
