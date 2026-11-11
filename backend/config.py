"""全局配置。

配置分为两类：
1. **部署配置**：数据目录、端口等，来自环境变量，进程启动后不变；
2. **运行设置**：引擎、密钥、并发数等，保存在数据库 ``settings`` 表，可在界面修改。

所有路径均使用 :class:`pathlib.Path`，避免 Windows 反斜杠转义问题。
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 应用元信息
# ---------------------------------------------------------------------------

APP_NAME = "识文台 InsightDesk"
APP_SLUG = "insightdesk"
APP_DESCRIPTION = "OCR + AI 智能文字工作台：识别、翻译、摘要、检索与导出"
VERSION = "1.0.0"
API_PREFIX = "/api"

# ---------------------------------------------------------------------------
# 目录与文件
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

#: 数据目录，可通过环境变量重定向（便于测试与多实例部署）
DATA_DIR = Path(os.environ.get("INSIGHTDESK_DATA_DIR", BASE_DIR / "data")).expanduser().resolve()

UPLOAD_DIR = DATA_DIR / "uploads"
THUMB_DIR = DATA_DIR / "thumbs"
EXPORT_DIR = DATA_DIR / "exports"
LOG_DIR = DATA_DIR / "logs"
BACKUP_DIR = DATA_DIR / "backups"
DB_PATH = DATA_DIR / "insightdesk.db"

FRONTEND_DIR = BASE_DIR / "frontend"

#: 数据目录内的所有子目录，启动时自动创建
DATA_SUBDIRS = (DATA_DIR, UPLOAD_DIR, THUMB_DIR, EXPORT_DIR, LOG_DIR, BACKUP_DIR)

# ---------------------------------------------------------------------------
# 上传限制
# ---------------------------------------------------------------------------

#: 允许的图片扩展名（小写，含点）
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}

#: Pillow 可识别的格式到扩展名的映射
PIL_FORMAT_EXT = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tif",
    "GIF": ".gif",
}

DEFAULT_MAX_FILE_MB = 20
MAX_IMAGE_PIXELS = 40_000_000  # 防止解压炸弹
THUMBNAIL_SIZE = (480, 480)

# ---------------------------------------------------------------------------
# 默认运行设置
# ---------------------------------------------------------------------------

#: 写入 settings 表的默认键值。新增配置项时在此登记即可自动获得默认值。
DEFAULT_SETTINGS: dict[str, object] = {
    # 引擎
    "ocr_engine": "mock",
    "ocr_language": "auto",
    "ai_provider": "mock",
    "ai_model": "deepseek-chat",
    "ai_base_url": "https://api.deepseek.com/v1",
    "ai_temperature": 0.3,
    "ai_max_tokens": 2048,
    # 任务
    "concurrency": 3,
    "max_retries": 2,
    "request_timeout": 45,
    "max_file_mb": DEFAULT_MAX_FILE_MB,
    "retry_backoff": 1.5,
    # 网页提取
    "auto_open_web": True,
    "web_timeout": 20,
    "web_max_bytes": 3_000_000,
    # 界面
    "theme": "dark",
    "ui_language": "zh",
    "default_export_format": "txt",
    "editor_auto_save": True,
    # 数据
    "keep_uploads_days": 30,
    "history_page_size": 20,
    # 云端 OCR 凭据
    "baidu_api_key": "",
    "baidu_secret_key": "",
    "tencent_secret_id": "",
    "tencent_secret_key": "",
    "tencent_region": "ap-guangzhou",
    # AI 凭据
    "ai_api_key": "",
}

#: 需要脱敏返回的配置键
SECRET_SETTING_KEYS = {
    "baidu_api_key",
    "baidu_secret_key",
    "tencent_secret_id",
    "tencent_secret_key",
    "ai_api_key",
}

#: 掩码占位符：前端提交该值表示"保持原值不变"
SECRET_MASK = "••••••••"

#: 数值型配置的取值范围，用于校验
SETTING_RANGES: dict[str, tuple[float, float]] = {
    "concurrency": (1, 8),
    "max_retries": (0, 5),
    "request_timeout": (5, 300),
    "max_file_mb": (1, 100),
    "retry_backoff": (1.0, 5.0),
    "web_timeout": (3, 120),
    "web_max_bytes": (100_000, 20_000_000),
    "ai_temperature": (0.0, 2.0),
    "ai_max_tokens": (64, 16384),
    "keep_uploads_days": (1, 3650),
    "history_page_size": (5, 100),
}

# ---------------------------------------------------------------------------
# 其它常量
# ---------------------------------------------------------------------------

#: 网页抓取 User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 InsightDesk/1.0"
)

#: 演示引擎的标识
MOCK_OCR_ENGINE = "mock"
MOCK_AI_PROVIDER = "mock"


def ensure_dirs() -> None:
    """创建数据目录及其子目录（幂等）。"""

    for directory in DATA_SUBDIRS:
        directory.mkdir(parents=True, exist_ok=True)


def is_desktop_mode() -> bool:
    """是否以桌面模式运行（由桌面启动器设置环境变量）。"""

    return os.environ.get("INSIGHTDESK_DESKTOP") == "1"


def data_path(relative: str | None) -> Path | None:
    """把数据库中的相对路径转换为绝对路径。

    数据库中只保存相对于数据目录的相对路径，避免迁移目录后失效。
    """

    if not relative:
        return None
    candidate = (DATA_DIR / relative).resolve()
    try:
        candidate.relative_to(DATA_DIR)
    except ValueError:
        # 防御路径穿越：非法路径直接返回 None
        return None
    return candidate
