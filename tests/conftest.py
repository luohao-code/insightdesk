"""pytest 公共夹具。

在导入任何 backend 模块之前重定向数据目录，确保测试不污染开发数据。
"""

from __future__ import annotations

import io
import os
import tempfile
import time
from pathlib import Path

import pytest

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="insightdesk_test_"))
os.environ["INSIGHTDESK_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ.pop("INSIGHTDESK_DESKTOP", None)

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from backend.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def image_bytes() -> bytes:
    """生成一张带中英文文字的 PNG，用于上传测试。"""

    image = Image.new("RGB", (960, 480), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=36)
    except TypeError:  # 旧版 Pillow
        font = ImageFont.load_default()
    draw.text((40, 60), "InsightDesk OCR Test 2026", fill="black", font=font)
    draw.text((40, 140), "Software Engineering Project", fill="black", font=font)
    draw.text((40, 220), "Batch processing and AI summary.", fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def uploaded_image(client, image_bytes) -> dict:
    response = client.post(
        "/api/ocr/upload",
        files={"files": ("sample.png", image_bytes, "image/png")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["images"], payload
    return payload["images"][0]


@pytest.fixture()
def document(client, uploaded_image) -> dict:
    response = client.post("/api/ocr/recognize", json={"image_id": uploaded_image["id"]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["document_id"], result
    return result


def wait_for_batch(client, batch_id: int, timeout: float = 30.0) -> dict:
    """轮询批次直到结束，返回批次详情。"""

    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/tasks/batches/{batch_id}")
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in {"succeeded", "failed", "partial", "cancelled"}:
            return last
        time.sleep(0.15)
    raise AssertionError(f"批次 {batch_id} 超时未完成：{last}")
