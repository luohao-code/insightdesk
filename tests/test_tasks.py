"""批量任务接口测试。"""

from __future__ import annotations

from tests.conftest import wait_for_batch


def _upload_many(client, image_bytes, count: int) -> list[dict]:
    images = []
    for index in range(count):
        response = client.post(
            "/api/ocr/upload",
            files={"files": (f"batch_{index}.png", image_bytes, "image/png")},
        )
        assert response.status_code == 200, response.text
        images.append(response.json()["images"][0])
    return images


def test_create_batch_and_finish(client, image_bytes):
    images = _upload_many(client, image_bytes, 3)
    response = client.post(
        "/api/tasks/batches",
        json={
            "images": [{"image_id": item["id"], "filename": item["filename"]} for item in images],
            "engine": "mock",
            "concurrency": 2,
            "name": "测试批次",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["accepted"] == 3
    batch_id = payload["batch"]["id"]

    detail = wait_for_batch(client, batch_id)
    assert detail["status"] == "succeeded"
    assert detail["total"] == 3
    assert detail["succeeded"] == 3
    assert detail["failed"] == 0
    assert len(detail["tasks"]) == 3
    assert all(task["status"] == "succeeded" for task in detail["tasks"])
    assert all(task["document_id"] for task in detail["tasks"])


def test_batch_list_contains_created(client, image_bytes):
    images = _upload_many(client, image_bytes, 1)
    created = client.post(
        "/api/tasks/batches",
        json={"images": [{"image_id": images[0]["id"]}], "name": "列表测试"},
    ).json()
    wait_for_batch(client, created["batch"]["id"])

    response = client.get("/api/tasks/batches?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["id"] == created["batch"]["id"] for item in payload["items"])


def test_cancel_finished_batch_is_rejected(client, image_bytes):
    images = _upload_many(client, image_bytes, 1)
    created = client.post(
        "/api/tasks/batches",
        json={"images": [{"image_id": images[0]["id"]}]},
    ).json()
    batch_id = created["batch"]["id"]
    wait_for_batch(client, batch_id)

    response = client.post(f"/api/tasks/batches/{batch_id}/cancel")
    assert response.status_code == 400
    assert "结束" in response.json()["detail"]


def test_retry_without_failures_is_rejected(client, image_bytes):
    images = _upload_many(client, image_bytes, 1)
    created = client.post(
        "/api/tasks/batches",
        json={"images": [{"image_id": images[0]["id"]}]},
    ).json()
    batch_id = created["batch"]["id"]
    wait_for_batch(client, batch_id)

    response = client.post(f"/api/tasks/batches/{batch_id}/retry")
    assert response.status_code == 400
    assert "没有可重试" in response.json()["detail"]


def test_create_batch_with_invalid_image(client):
    response = client.post(
        "/api/tasks/batches",
        json={"images": [{"image_id": "ffffffffffffffff"}]},
    )
    assert response.status_code == 400


def test_task_summary(client):
    response = client.get("/api/tasks/summary")
    assert response.status_code == 200
    payload = response.json()
    assert "active_batches" in payload
    assert "subscribers" in payload
