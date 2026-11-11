"""ORM 模型集合。

导入本包即完成所有表到 SQLAlchemy 元数据的注册，
``backend.db.init_db`` 依赖这一点。
"""

from .ai import AIRun
from .conversation import Conversation, Message
from .document import Document
from .setting import Setting
from .task import Batch, Task
from .web import WebExtraction

__all__ = [
    "Document",
    "Batch",
    "Task",
    "AIRun",
    "WebExtraction",
    "Conversation",
    "Message",
    "Setting",
]
