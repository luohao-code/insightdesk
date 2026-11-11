"""通用工具：图片处理。

职责：
* 校验上传文件确实是图片（防止伪造扩展名）；
* 读取尺寸与格式；
* 生成缩略图；
* 按需预处理（EXIF 纠正、灰度、自动对比度、限制长边），提升 OCR 成功率。
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .. import config
from .files import ensure_dir

#: Pillow 解压炸弹保护阈值
Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS


class ImageError(ValueError):
    """图片校验或处理失败。"""


@dataclass(slots=True)
class ImageInfo:
    """图片元信息。"""

    width: int
    height: int
    format: str
    mode: str
    size_bytes: int

    @property
    def extension(self) -> str:
        return config.PIL_FORMAT_EXT.get(self.format.upper(), ".png")


def probe_image(path: Path) -> ImageInfo:
    """校验并读取图片元信息。"""

    if not path.exists() or not path.is_file():
        raise ImageError("图片文件不存在")
    size = path.stat().st_size
    if size == 0:
        raise ImageError("图片文件为空")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return ImageInfo(
                width=image.width,
                height=image.height,
                format=(image.format or "PNG").upper(),
                mode=image.mode,
                size_bytes=size,
            )
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageError("文件不是有效的图片或已损坏") from exc


def load_image(path: Path) -> Image.Image:
    """打开图片并纠正 EXIF 方向。"""

    image = Image.open(path)
    image.load()
    return ImageOps.exif_transpose(image)


def make_thumbnail(source: Path, target: Path, size: tuple[int, int] = config.THUMBNAIL_SIZE) -> Path:
    """生成等比缩略图（保留透明通道）。"""

    ensure_dir(target.parent)
    with load_image(source) as image:
        thumb = image.copy()
        thumb.thumbnail(size, Image.Resampling.LANCZOS)
        if thumb.mode not in ("RGB", "RGBA"):
            thumb = thumb.convert("RGBA" if "A" in thumb.getbands() else "RGB")
        thumb.save(target, format="PNG", optimize=True)
    return target


def preprocess_image(
    source: Path,
    target: Path,
    *,
    grayscale: bool = False,
    autocontrast: bool = False,
    max_long_edge: int = 2400,
    rotate_degrees: float = 0.0,
) -> Path:
    """OCR 前的轻量预处理。

    * 限制长边，降低大图识别耗时；
    * 可选灰度与自动对比度，改善低质量扫描件；
    * 可选旋转（用户手动纠正方向）。
    """

    ensure_dir(target.parent)
    with load_image(source) as image:
        processed = image.copy()
        if rotate_degrees:
            processed = processed.rotate(-abs(rotate_degrees), expand=True, fillcolor="white")
        if max(processed.size) > max_long_edge:
            ratio = max_long_edge / max(processed.size)
            processed = processed.resize(
                (max(1, int(processed.width * ratio)), max(1, int(processed.height * ratio))),
                Image.Resampling.LANCZOS,
            )
        if grayscale:
            processed = processed.convert("L")
            if autocontrast:
                processed = ImageOps.autocontrast(processed)
            processed = processed.convert("RGB")
        elif autocontrast:
            processed = ImageOps.autocontrast(processed.convert("RGB"))
        processed.save(target, format="PNG")
    return target


def image_to_base64(path: Path, max_bytes: int = 8_000_000) -> str:
    """读取图片并编码为 base64（云端 OCR 接口使用）。"""

    data = path.read_bytes()
    if len(data) > max_bytes:
        # 过大时先压缩，避免云端请求体超限
        with load_image(path) as image:
            image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=88)
            data = buffer.getvalue()
    return base64.b64encode(data).decode("ascii")


def guess_image_suffix(data: bytes) -> str | None:
    """根据文件头猜测扩展名（上传时二次校验）。"""

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"BM"):
        return ".bmp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return ".tif"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    return None
