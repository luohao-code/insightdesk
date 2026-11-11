"""上传图片管理。

所有上传文件以随机 ID 命名，数据库中仅保存相对路径，
避免原始文件名带来的路径穿越、编码与重名问题。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .. import config
from ..utils.files import ensure_dir, random_id, relative_path, write_bytes
from ..utils.images import ImageError, guess_image_suffix, make_thumbnail, probe_image
from ..utils.security import SecurityError, safe_join
from ..utils.time import now_iso

_ID_RE = re.compile(r"^[a-f0-9]{8,64}$")


class UploadError(ValueError):
    """上传校验失败。"""


def _existing_upload(image_id: str) -> Path | None:
    if not _ID_RE.match(image_id or ""):
        raise SecurityError("非法的图片标识")
    for path in config.UPLOAD_DIR.glob(f"{image_id}.*"):
        if path.is_file() and path.suffix.lower() != ".part":
            return path
    return None


def save_bytes(data: bytes, filename: str, max_mb: int | None = None) -> dict:
    """保存上传图片并生成缩略图。

    :returns: 包含 id、路径、尺寸等信息
    :raises UploadError: 文件为空、超限、不是有效图片
    """

    limit = (max_mb or config.DEFAULT_MAX_FILE_MB) * 1024 * 1024
    if not data:
        raise UploadError("文件为空")
    if len(data) > limit:
        raise UploadError(f"文件超过 {max_mb or config.DEFAULT_MAX_FILE_MB}MB 上限")

    suffix = guess_image_suffix(data)
    if not suffix:
        raise UploadError("仅支持 PNG/JPG/WEBP/BMP/TIFF/GIF 图片")

    ensure_dir(config.UPLOAD_DIR)
    image_id = random_id(24)
    target = config.UPLOAD_DIR / f"{image_id}{suffix}"
    write_bytes(target, data)

    try:
        info = probe_image(target)
    except ImageError as exc:
        target.unlink(missing_ok=True)
        raise UploadError(str(exc)) from exc

    thumb = config.THUMB_DIR / f"{image_id}.png"
    try:
        make_thumbnail(target, thumb)
    except Exception:
        thumb = None  # 缩略图失败不影响主流程

    return {
        "id": image_id,
        "filename": filename or target.name,
        "path": target,
        "thumb": thumb,
        "width": info.width,
        "height": info.height,
        "size_bytes": info.size_bytes,
        "format": info.format,
        "uploaded_at": now_iso(),
    }


def save_path(source: Path, filename: str | None = None) -> dict:
    """把本地文件（文件夹批量）复制为受管理的上传文件。"""

    data = source.read_bytes()
    return save_bytes(data, filename or source.name)


def get_path(image_id: str) -> Path:
    path = _existing_upload(image_id)
    if path is None:
        raise UploadError("图片不存在或已被清理")
    return path


def get_thumb(image_id: str) -> Path | None:
    path = config.THUMB_DIR / f"{image_id}.png"
    if path.exists():
        return path
    source = _existing_upload(image_id)
    if source is None:
        return None
    try:
        make_thumbnail(source, path)
        return path
    except Exception:
        return source


def to_public(image_id: str, filename: str = "", info: dict | None = None) -> dict:
    """构造返回给前端的元信息。"""

    from .serializers import upload_thumb_url, upload_url

    payload = {
        "id": image_id,
        "filename": filename,
        "width": 0,
        "height": 0,
        "size_bytes": 0,
        "format": "PNG",
        "url": upload_url(image_id),
        "thumbnail_url": upload_thumb_url(image_id),
        "uploaded_at": now_iso(),
    }
    if info:
        payload.update(
            {
                "filename": info.get("filename") or filename,
                "width": info.get("width", 0),
                "height": info.get("height", 0),
                "size_bytes": info.get("size_bytes", 0),
                "format": info.get("format", "PNG"),
                "uploaded_at": info.get("uploaded_at", payload["uploaded_at"]),
            }
        )
    return payload


def store_to_uploads(source: Path, image_id: str | None = None) -> tuple[str, Path]:
    """把一个外部路径登记为上传文件（已在上传目录内则原地保留）。"""

    source = source.resolve()
    try:
        source.relative_to(config.UPLOAD_DIR.resolve())
        return source.stem, source
    except ValueError:
        pass
    ensure_dir(config.UPLOAD_DIR)
    new_id = image_id or random_id(24)
    suffix = source.suffix.lower() or ".png"
    target = safe_join(config.UPLOAD_DIR, f"{new_id}{suffix}")
    shutil.copyfile(source, target)
    return new_id, target


def relative(path: Path | None) -> str | None:
    return relative_path(path)
