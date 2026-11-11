"""OCR 上传与识别接口测试。"""

from __future__ import annotations


def test_engines_catalog(client):
    response = client.get("/api/ocr/engines")
    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["items"]}
    assert {"mock", "rapidocr", "baidu", "tencent"} <= names
    mock = next(item for item in payload["items"] if item["name"] == "mock")
    assert mock["available"] is True


def test_upload_and_fetch_media(client, uploaded_image):
    assert uploaded_image["width"] > 0
    assert uploaded_image["height"] > 0
    assert uploaded_image["url"].startswith("/api/media/upload/")

    image_response = client.get(uploaded_image["url"])
    assert image_response.status_code == 200
    assert image_response.headers["content-type"].startswith("image/")

    thumb_response = client.get(uploaded_image["thumbnail_url"])
    assert thumb_response.status_code == 200


def test_upload_rejects_non_image(client):
    response = client.post(
        "/api/ocr/upload",
        files={"files": ("note.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400
    assert "图片" in response.json()["detail"]


def test_recognize_creates_document(client, document, uploaded_image):
    assert document["text"]
    assert document["document_id"]
    assert document["char_count"] > 0
    assert document["engine"] == "mock"
    assert document["demo"] is True

    detail = client.get(f"/api/history/{document['document_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["source_type"] == "image"
    assert payload["content"] == document["text"]
    assert payload["thumbnail_url"]


def test_recognize_unknown_image(client):
    response = client.post("/api/ocr/recognize", json={"image_id": "deadbeef" * 4})
    assert response.status_code == 404


def test_recognize_invalid_payload(client):
    response = client.post("/api/ocr/recognize", json={"image_id": "x"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation"


def test_recognize_english_option(client, uploaded_image):
    response = client.post(
        "/api/ocr/recognize",
        json={"image_id": uploaded_image["id"], "language": "en", "grayscale": True},
    )
    assert response.status_code == 200
    assert response.json()["text"]


def test_document_patch_and_delete(client, document):
    document_id = document["document_id"]
    patched = client.patch(
        f"/api/history/{document_id}",
        json={"title": "新的标题", "tags": ["课程", "OCR"], "favorite": True},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "新的标题"
    assert "课程" in patched.json()["tags"]
    assert patched.json()["favorite"] is True

    deleted = client.delete(f"/api/history/{document_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/history/{document_id}").status_code == 404
