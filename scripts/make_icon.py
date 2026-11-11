"""生成 Windows 应用图标（desktop/icon.ico）。

不依赖 SVG 渲染库，直接使用 Pillow 绘制与品牌一致的图形。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent.parent
TARGET = BASE_DIR / "desktop" / "icon.ico"


def draw_icon(size: int = 256) -> Image.Image:
    scale = size / 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # 圆角深色背景
    margin = int(8 * scale)
    draw.rounded_rectangle(
        [(margin, margin), (size - margin, size - margin)],
        radius=int(56 * scale),
        fill=(11, 18, 32, 255),
    )

    # 渐变感边框（用两段颜色模拟）
    draw.rounded_rectangle(
        [(int(18 * scale), int(20 * scale)), (size - int(18 * scale), size - int(20 * scale))],
        radius=int(40 * scale),
        outline=(129, 140, 248, 255),
        width=max(2, int(7 * scale)),
    )

    # 文字线条
    line_color = (199, 210, 254, 255)
    width = max(2, int(9 * scale))
    for index, (start, end) in enumerate([(72, 184), (72, 140), (72, 160)]):
        y = int((92 + index * 38) * scale)
        draw.line(
            [(int(62 * scale), y), (int(end * scale), y)],
            fill=line_color if index else (255, 255, 255, 255),
            width=width,
        )

    # 青色强调点
    draw.ellipse(
        [
            (int(178 * scale), int(156 * scale)),
            (int(214 * scale), int(192 * scale)),
        ],
        fill=(34, 211, 238, 255),
    )
    return image


def main() -> Path:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_icon(size) for size in sizes]
    images[-1].save(TARGET, format="ICO", sizes=[(size, size) for size in sizes], append_images=images[:-1])
    print(f"saved: {TARGET}")
    return TARGET


if __name__ == "__main__":
    main()
