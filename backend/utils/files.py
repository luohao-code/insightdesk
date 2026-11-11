"""通用工具：文件与路径。"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections.abc import Iterator
from pathlib import Path

from .. import config

_UNSAFE_NAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def random_id(length: int = 16) -> str:
    """生成 URL 安全的随机标识（用于上传文件与任务）。"""

    return secrets.token_hex(max(4, length // 2))


def safe_filename(name: str | None, fallback: str = "image") -> str:
    """清洗用户提供的文件名，去掉路径与非法字符，防止路径穿越。"""

    raw = Path(name or "").name
    raw = _UNSAFE_NAME_RE.sub("_", raw).strip(" .")
    if not raw:
        return fallback
    stem = Path(raw).stem[:80] or fallback
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"_{stem}"
    suffix = Path(raw).suffix.lower()
    return f"{stem}{suffix}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_bytes(path: Path, data: bytes) -> Path:
    """原子写入：先写临时文件再替换，避免半截文件。"""

    ensure_dir(path.parent)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(data)
    temporary.replace(path)
    return path


def write_json(path: Path, payload: object) -> Path:
    return write_bytes(path, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))


def read_json(path: Path, default: object = None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def sha1_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(path: Path | str | None) -> str | None:
    """把绝对路径转换为相对于数据目录的 POSIX 路径（存库用）。"""

    if not path:
        return None
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(config.DATA_DIR).as_posix()
    except ValueError:
        return resolved.as_posix()


def abs_path(relative: str | None) -> Path | None:
    """把库中的相对路径还原为绝对路径，并校验未被越权。"""

    if not relative:
        return None
    candidate = (config.DATA_DIR / relative).resolve()
    try:
        candidate.relative_to(config.DATA_DIR.resolve())
    except ValueError:
        return None
    return candidate


def human_size(size: int | float | None) -> str:
    if not size:
        return "0 B"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def is_image_name(name: str | None) -> bool:
    return bool(name) and Path(name).suffix.lower() in config.IMAGE_EXTENSIONS


def iter_images(folder: Path, recursive: bool = True, limit: int = 500) -> Iterator[Path]:
    """遍历目录中的图片文件。

    * 默认递归子目录；
    * 忽略隐藏目录（以 ``.`` 开头）；
    * 结果按路径排序，保证批次顺序稳定；
    * 最多返回 ``limit`` 个文件，防止误选超大目录。
    """

    if not folder.exists() or not folder.is_dir():
        return
    pattern = "**/*" if recursive else "*"
    count = 0
    for path in sorted(folder.glob(pattern)):
        if count >= limit:
            return
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(folder).parts):
            continue
        if path.suffix.lower() in config.IMAGE_EXTENSIONS:
            yield path
            count += 1


def remove_quiet(path: Path | None) -> None:
    """静默删除文件，忽略异常（清理场景使用）。"""

    if not path:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """在目录下生成不冲突的文件路径。"""

    ensure_dir(directory)
    candidate = directory / f"{stem}{suffix}"
    index = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{index}{suffix}"
        index += 1
    return candidate


def format_timestamp_for_filename() -> str:
    from .time import now

    return now().strftime("%Y%m%d_%H%M%S")
