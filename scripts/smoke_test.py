"""端到端冒烟测试脚本。

不依赖 pytest，直接使用 Starlette TestClient 走一遍核心链路：

    健康检查 → 上传 → OCR → 历史 → AI 摘要 → 导出

用法::

    python scripts/smoke_test.py
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# 使用独立数据目录，避免污染开发数据
_TEMP_DATA = Path(tempfile.mkdtemp(prefix="insightdesk_smoke_"))
os.environ["INSIGHTDESK_DATA_DIR"] = str(_TEMP_DATA)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402


def make_image() -> bytes:
    image = Image.new("RGB", (900, 420), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=40)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((40, 60), "InsightDesk OCR Workbench", fill="black", font=font)
    draw.text((40, 140), "Software Engineering Project 2026", fill="black", font=font)
    draw.text((40, 220), "Batch processing, AI summary, export.", fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def main() -> int:
    from fastapi.testclient import TestClient

    from backend.main import app

    failures: list[str] = []
    with TestClient(app) as client:
        health = client.get("/api/health")
        print("health:", health.status_code, health.json().get("status"))
        if health.status_code != 200:
            failures.append("健康检查失败")

        upload = client.post(
            "/api/ocr/upload",
            files={"files": ("sample.png", make_image(), "image/png")},
        )
        print("upload:", upload.status_code, upload.json())
        if upload.status_code != 200 or not upload.json().get("images"):
            failures.append("上传失败")
            image_id = None
        else:
            image_id = upload.json()["images"][0]["id"]

        if image_id:
            recognize = client.post("/api/ocr/recognize", json={"image_id": image_id})
            payload = recognize.json()
            print("recognize:", recognize.status_code, payload.get("engine"), payload.get("char_count"))
            if recognize.status_code != 200 or not payload.get("text"):
                failures.append("OCR 识别失败")
                document_id = None
            else:
                document_id = payload.get("document_id")

            history = client.get("/api/history", params={"q": "InsightDesk"})
            print("history search:", history.status_code, history.json().get("total"))
            if history.status_code != 200:
                failures.append("历史检索失败")

            if document_id:
                ai = client.post(
                    "/api/ai/process",
                    json={"action": "summarize", "document_id": document_id, "options": {}},
                )
                print("ai:", ai.status_code, (ai.json().get("output") or "")[:60].replace("\n", " "))
                if ai.status_code != 200:
                    failures.append("AI 处理失败")

                export = client.post(
                    "/api/export",
                    json={"ids": [document_id], "format": "txt"},
                )
                print("export:", export.status_code, len(export.content), "bytes")
                if export.status_code != 200 or not export.content:
                    failures.append("导出失败")

        settings = client.get("/api/settings")
        values = settings.json().get("values", {})
        print("settings:", settings.status_code, "masked keys:", settings.json().get("secrets_masked"))
        if "ai_api_key" in values and values["ai_api_key"]:
            failures.append("密钥未脱敏")

        stats = client.get("/api/stats/overview")
        print("stats:", stats.status_code, stats.json().get("documents"))

    if failures:
        print("\n冒烟测试失败：", "；".join(failures))
        return 1
    print("\n冒烟测试全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
