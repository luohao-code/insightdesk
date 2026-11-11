"""历史记录检索与管理测试。"""

from __future__ import annotations


def _make_document(client, uploaded_image, title: str) -> int:
    response = client.post(
        "/api/ocr/recognize",
        json={"image_id": uploaded_image["id"]},
    )
    assert response.status_code == 200
    document_id = response.json()["document_id"]
    patched = client.patch(f"/api/history/{document_id}", json={"title": title, "tags": ["检索测试"]})
    assert patched.status_code == 200
    return document_id


def test_search_by_title(client, uploaded_image):
    document_id = _make_document(client, uploaded_image, "唯一检索词ABC123")
    response = client.get("/api/history", params={"q": "唯一检索词"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["id"] == document_id for item in payload["items"])
    assert payload["took_ms"] >= 0


def test_filter_by_source_and_favorite(client, document):
    document_id = document["document_id"]
    client.patch(f"/api/history/{document_id}", json={"favorite": True})

    response = client.get("/api/history", params={"source_type": "image", "favorite": "true"})
    assert response.status_code == 200
    payload = response.json()
    assert all(item["favorite"] for item in payload["items"])
    assert all(item["source_type"] == "image" for item in payload["items"])


def test_filter_by_engine(client, document):
    response = client.get("/api/history", params={"engine": "mock"})
    assert response.status_code == 200
    assert all(item["engine"] == "mock" for item in response.json()["items"])


def test_pagination(client, uploaded_image):
    for index in range(3):
        _make_document(client, uploaded_image, f"分页测试 {index}")

    response = client.get("/api/history", params={"page": 1, "page_size": 2, "sort": "created_desc"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) <= 2
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["pages"] >= 1


def test_tags_and_stats(client, document):
    client.patch(f"/api/history/{document['document_id']}", json={"tags": ["课程", "OCR", "课程"]})
    tags = client.get("/api/history/tags")
    assert tags.status_code == 200
    names = {item["tag"] for item in tags.json()["items"]}
    assert "课程" in names
    assert "OCR" in names

    stats = client.get("/api/history/stats")
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["total"] >= 1
    assert "mock" in payload["engines"]


def test_update_title_and_content(client, document):
    document_id = document["document_id"]
    updated = client.patch(
        f"/api/history/{document_id}",
        json={"title": "修改后的标题", "content": "新的正文内容", "tags": ["手动编辑"]},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["title"] == "修改后的标题"
    assert payload["content"] == "新的正文内容"
    assert payload["char_count"] == 6
    assert payload["version"] >= 2


def test_detail_not_found(client):
    assert client.get("/api/history/999999").status_code == 404


def test_bulk_delete(client, uploaded_image):
    ids = [_make_document(client, uploaded_image, f"批量删除 {index}") for index in range(2)]
    response = client.post("/api/history/bulk-delete", json={"ids": ids})
    assert response.status_code == 200
    assert response.json()["deleted"] == 2
    for document_id in ids:
        assert client.get(f"/api/history/{document_id}").status_code == 404


def test_invalid_sort_falls_back(client):
    response = client.get("/api/history", params={"sort": "not-a-sort"})
    assert response.status_code == 200
