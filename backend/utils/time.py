"""通用工具：时间处理。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

#: 中国标准时间（UTC+8）。界面展示统一使用本地时区。
CST = timezone(timedelta(hours=8), name="Asia/Shanghai")


def now() -> datetime:
    """当前时间（带时区）。"""

    return datetime.now(tz=CST)


def now_iso() -> str:
    """当前时间的 ISO 字符串，精确到秒。"""

    return now().replace(microsecond=0).isoformat()


def today_key() -> str:
    """返回 ``YYYY-MM-DD``，用于按日统计。"""

    return now().strftime("%Y-%m-%d")


def date_key(moment: datetime) -> str:
    return moment.astimezone(CST).strftime("%Y-%m-%d")


def parse_iso(value: str | None) -> datetime | None:
    """解析 ISO 时间字符串，失败返回 ``None``。"""

    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CST)
    return parsed


def human_duration(milliseconds: float | int | None) -> str:
    """把毫秒转换为易读字符串。"""

    if milliseconds is None:
        return "-"
    ms = float(milliseconds)
    if ms < 1000:
        return f"{ms:.0f} ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    minutes = int(seconds // 60)
    remain = int(seconds % 60)
    return f"{minutes} 分 {remain} 秒"


def recent_days(count: int = 7) -> list[str]:
    """返回最近 ``count`` 天的日期键（含今天，按时间升序）。"""

    current = now()
    return [(current - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(count - 1, -1, -1)]


def iso_days_ago(days: int) -> str:
    """返回 N 天前的 ISO 时间。"""

    return (now() - timedelta(days=days)).replace(microsecond=0).isoformat()
