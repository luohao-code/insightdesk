"""设置服务。

* 读取时合并默认值，保证新增配置项对老数据库也生效；
* 密钥类配置返回时脱敏，提交掩码值表示"保持不变"；
* 数值配置做范围校验，防止前端传入危险值（例如并发 999）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Setting
from ..utils.security import is_masked, mask_secret
from ..utils.time import now_iso


class SettingsError(ValueError):
    """设置项非法。"""


def get_all(db: Session) -> dict:
    """返回完整配置（含明文密钥，仅供服务端内部使用）。"""

    values = dict(config.DEFAULT_SETTINGS)
    for row in db.scalars(select(Setting)).all():
        if row.key in values:
            values[row.key] = row.parsed
    return values


def get_value(db: Session, key: str, default=None):
    values = get_all(db)
    return values.get(key, default)


def get_int(db: Session, key: str, default: int = 0) -> int:
    try:
        return int(get_value(db, key, default))
    except (TypeError, ValueError):
        return default


def get_float(db: Session, key: str, default: float = 0.0) -> float:
    try:
        return float(get_value(db, key, default))
    except (TypeError, ValueError):
        return default


def get_bool(db: Session, key: str, default: bool = False) -> bool:
    value = get_value(db, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce(key: str, value):
    default = config.DEFAULT_SETTINGS[key]
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise SettingsError(f"{key} 必须是整数") from exc
    if isinstance(default, float):
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise SettingsError(f"{key} 必须是数字") from exc
    if isinstance(default, str):
        return str(value).strip()
    return value


def update(db: Session, incoming: dict) -> dict:
    """增量更新配置，返回更新后的完整配置（含明文，调用方决定如何返回）。"""

    if not isinstance(incoming, dict) or not incoming:
        raise SettingsError("没有需要更新的配置")

    current = get_all(db)
    prepared: dict[str, object] = {}
    skipped_secrets = 0

    for key, raw_value in incoming.items():
        if key not in config.DEFAULT_SETTINGS:
            continue
        if key in config.SECRET_SETTING_KEYS:
            if raw_value is None or is_masked(str(raw_value)):
                skipped_secrets += 1
                continue
        value = _coerce(key, raw_value)

        if key in config.SETTING_RANGES:
            low, high = config.SETTING_RANGES[key]
            if not (low <= float(value) <= high):
                raise SettingsError(f"{key} 需在 {low}–{high} 之间")

        if key == "ocr_engine":
            from ..providers import ocr_providers

            if value not in ocr_providers():
                raise SettingsError(f"未知的 OCR 引擎：{value}")
        if key == "ai_provider":
            from ..providers import ai_providers

            if value not in ai_providers():
                raise SettingsError(f"未知的 AI 引擎：{value}")
        if key in {"theme", "ui_language", "ocr_language", "default_export_format"}:
            allowed = {
                "theme": {"dark", "light", "system"},
                "ui_language": {"zh", "en"},
                "ocr_language": {"auto", "zh", "en"},
                "default_export_format": {"txt", "csv", "md", "docx", "xlsx", "json", "zip"},
            }[key]
            if value not in allowed:
                raise SettingsError(f"{key} 的取值不合法：{value}")

        prepared[key] = value

    if not prepared:
        # 只提交了掩码密钥，视为"保持不变"的幂等请求
        if skipped_secrets:
            return current
        raise SettingsError("没有有效的配置项")

    for key, value in prepared.items():
        row = db.get(Setting, key)
        if row is None:
            row = Setting(key=key)
            row.parsed = value
            db.add(row)
        else:
            row.parsed = value
            row.updated_at = now_iso()

    db.commit()
    current.update(prepared)
    return current


def masked_view(db: Session) -> dict:
    """面向浏览器的视图：密钥脱敏，并标记哪些项已配置。"""

    values = get_all(db)
    masked: list[str] = []
    for key in config.SECRET_SETTING_KEYS:
        if values.get(key):
            values[key] = config.SECRET_MASK
            masked.append(key)
        else:
            values[key] = ""

    # 附带引擎可用性，前端一次性渲染设置页
    from ..providers import ai_catalog, ocr_catalog

    return {"values": values, "secrets_masked": masked, "engines": {"ocr": ocr_catalog(values), "ai": ai_catalog(values)}}


def provider_settings(db: Session) -> dict:
    """引擎调用所需的完整配置。"""

    return get_all(db)


def secret_hint(value: str | None) -> str:
    return mask_secret(value) if value else ""
