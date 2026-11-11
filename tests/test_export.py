"""导出接口测试。"""

from __future__ import annotations

import csv
import io
import json
import zipfile

import pytest


@pytest.mark.parametrize(
    "fmt,content_type,prefix",
    [
        ("txt", "text/plain", b""),
        ("csv", "text/csv", b"\xef\xbb\xbf"),
        ("md", "text/markdown", b"#"),
        ("json", "application/json", b"["),
        ("docx", "wordprocessingml", b"PK"),
        ("xlsx", "spreadsheetml", b"PK"),
        ("zip", "application/zip", b"PK"),
    ],
)
def test_export_formats(client, document, fmt, content_type, prefix):
    response = client.post("/api/export", json={"ids": [document["document_id"]], "format": fmt})
    assert response.status_code == 200, response.text
    assert content_type in response.headers["content-type"]
    assert response.content
    if prefix:
        assert response.content.startswith(prefix)
    assert "attachment" in response.headers["content-disposition"]


def test_export_csv_content(client, document):
    response = client.post("/api/export", json={"ids": [document["document_id"]], "format": "csv"})
    text = response.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][0] == "ID"
    assert len(rows) == 2


def test_export_json_content(client, document):
    response = client.post("/api/export", json={"ids": [document["document_id"]], "format": "json"})
    payload = json.loads(response.content.decode("utf-8"))
    assert isinstance(payload, list)
    assert payload[0]["id"] == document["document_id"]


def test_export_zip_contains_manifest(client, document):
    response = client.post("/api/export", json={"ids": [document["document_id"]], "format": "zip"})
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    assert "manifest.csv" in names
    assert any(name.endswith(".txt") for name in names)


def test_export_multiple_documents(client, document):
    second = client.post(
        "/api/ai/process",
        json={"action": "summarize", "document_id": document["document_id"]},
    )
    assert second.status_code == 200
    response = client.post(
        "/api/export",
        json={"ids": [document["document_id"], document["document_id"]], "format": "txt"},
    )
    assert response.status_code == 200
    assert response.headers["X-Export-Count"] == "1"


def test_export_unknown_format(client, document):
    response = client.post(
        "/api/export",
        json={"ids": [document["document_id"]], "format": "pdf"},
    )
    assert response.status_code == 400
    assert "不支持" in response.json()["detail"]


def test_export_missing_document(client):
    response = client.post("/api/export", json={"ids": [999999], "format": "txt"})
    assert response.status_code == 400


def test_export_formats_endpoint(client):
    response = client.get("/api/export/formats")
    assert response.status_code == 200
    formats = {item["format"] for item in response.json()["items"]}
    assert {"txt", "csv", "md", "docx", "xlsx", "json", "zip"} == formats
