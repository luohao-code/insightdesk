"""日志配置。

同时输出到控制台与 ``data/logs/app.log``（按大小滚动，最多保留 3 份）。
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .. import config


def setup_logging(level: int = logging.INFO) -> None:
    config.ensure_dirs()
    root = logging.getLogger()
    if getattr(root, "_insightdesk_configured", False):
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 桌面窗口模式（console=False）下 sys.stderr 为 None，跳过控制台输出
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    file_handler = RotatingFileHandler(
        config.LOG_DIR / "app.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    root._insightdesk_configured = True  # type: ignore[attr-defined]
