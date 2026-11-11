"""数据库连接与会话管理。

使用 SQLite + SQLAlchemy 2.0：

* 开启 WAL 模式，提升读写并发能力；
* 开启外键约束；
* 为历史记录建立 FTS5 虚拟表（trigram 分词，兼容中文子串检索），
  若当前 SQLite 不支持 trigram，则业务层自动降级为 LIKE 查询。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def _build_engine():
    config.ensure_dirs()
    return create_engine(
        f"sqlite:///{config.DB_PATH.as_posix()}",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record):  # pragma: no cover - 驱动回调
    """每次建立连接时设置 SQLite pragma。"""

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA temp_store=MEMORY")
    finally:
        cursor.close()


#: FTS 建表语句。content 与 tags 同步由触发器维护。
_FTS_STATEMENTS = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
        title, content, tags, tokenize='trigram'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS documents_fts_ai AFTER INSERT ON documents BEGIN
        INSERT INTO documents_fts(rowid, title, content, tags)
        VALUES (new.id, new.title, new.content, new.tags);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS documents_fts_ad AFTER DELETE ON documents BEGIN
        DELETE FROM documents_fts WHERE rowid = old.id;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS documents_fts_au AFTER UPDATE OF title, content, tags ON documents BEGIN
        DELETE FROM documents_fts WHERE rowid = old.id;
        INSERT INTO documents_fts(rowid, title, content, tags)
        VALUES (new.id, new.title, new.content, new.tags);
    END
    """,
)


def fts_available() -> bool:
    """检测当前数据库是否成功建立了 FTS5 索引。"""

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='documents_fts'")
            ).first()
            return row is not None
    except Exception:  # pragma: no cover - 环境相关
        return False


def init_db() -> None:
    """建表并初始化 FTS 索引。应用每次启动时调用，可重复执行。"""

    # 导入模型以注册元数据（避免循环导入，放在函数内）
    from . import models  # noqa: F401

    config.ensure_dirs()
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        for statement in _FTS_STATEMENTS:
            try:
                conn.execute(text(statement))
            except Exception as exc:  # pragma: no cover - 依赖 SQLite 版本
                logger.warning("初始化 FTS 失败，将降级为 LIKE 检索：%s", exc)
                break
        else:
            # 首次启用 FTS 时回填已有数据
            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO documents_fts(rowid, title, content, tags)
                        SELECT d.id, d.title, d.content, d.tags FROM documents d
                        WHERE d.id NOT IN (SELECT rowid FROM documents_fts)
                        """
                    )
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("回填 FTS 索引失败：%s", exc)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：提供请求级数据库会话。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """后台线程使用的会话上下文，自动提交/回滚。"""

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
