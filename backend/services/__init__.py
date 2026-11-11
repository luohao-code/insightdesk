"""业务服务层。

服务层职责：
* 组合多个模型与提供者完成一个完整业务用例；
* 处理事务、异常与日志；
* 不直接依赖 FastAPI，便于单元测试与命令行复用。
"""

from . import (
    ai_service,
    cleanup,
    events,
    export_service,
    history_service,
    image_service,
    ocr_service,
    serializers,
    settings_service,
    stats_service,
    task_service,
    web_extract_service,
)

__all__ = [
    "ai_service",
    "cleanup",
    "events",
    "export_service",
    "history_service",
    "image_service",
    "ocr_service",
    "serializers",
    "settings_service",
    "stats_service",
    "task_service",
    "web_extract_service",
]
