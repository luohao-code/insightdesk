"""网页提取与自动打开接口测试。"""

from __future__ import annotations

from backend.services import web_extract_service

HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <title>识文台项目介绍 - 示例站点</title>
  <meta property="og:title" content="识文台项目介绍" />
  <meta property="og:site_name" content="示例站点" />
  <meta name="author" content="罗浩" />
  <meta property="article:published_time" content="2026-09-08T10:00:00+08:00" />
  <meta property="og:image" content="/images/cover.png" />
</head>
<body>
  <nav><a href="/">首页</a><a href="/about">关于</a></nav>
  <article>
    <h1>识文台项目介绍</h1>
    <p>识文台是一套 OCR 与 AI 结合的文字工作台，支持批量识别、翻译、摘要、关键词与问答。</p>
    <p>系统提供网页提取能力，可以在提取完成后自动打开原始网页，方便用户对照阅读。</p>
    <p>所有数据保存在本机，密钥仅保存在服务端，接口返回时会自动脱敏。</p>
    <img src="/images/screenshot-1.png" alt="界面截图" />
    <img data-src="https://cdn.example.com/screenshot-2.png" alt="详情" />
  </article>
  <footer>版权所有 © 示例站点</footer>
</body>
</html>
"""


class FakeResponse:
    def __init__(self, text=HTML, status_code=200, headers=None, encoding="utf-8"):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.encoding = encoding
        self.apparent_encoding = "utf-8"

    def iter_content(self, chunk_size=65536):
        data = self.text.encode("utf-8")
        for index in range(0, len(data), chunk_size):
            yield data[index : index + chunk_size]

    def close(self):
        return None


def test_extract_rejects_localhost(client):
    response = client.post("/api/web/extract", json={"url": "http://127.0.0.1/"})
    assert response.status_code == 400
    assert "内网" in response.json()["detail"] or "本机" in response.json()["detail"]


def test_extract_rejects_non_http(client):
    response = client.post("/api/web/extract", json={"url": "file:///etc/passwd"})
    assert response.status_code == 400
    assert "http" in response.json()["detail"]


def test_extract_rejects_private_hostname(client):
    response = client.post("/api/web/extract", json={"url": "http://localhost/admin"})
    assert response.status_code == 400


def test_open_rejects_private_url(client):
    response = client.post("/api/web/open", json={"url": "http://192.168.1.10/"})
    assert response.status_code == 400


def test_open_in_server_mode(client):
    response = client.post("/api/web/open", json={"url": "https://example.com/article"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["opened"] is False
    assert payload["mode"] == "browser"


def test_extract_success(client, monkeypatch):
    monkeypatch.setattr(
        web_extract_service.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(),
    )
    response = client.post(
        "/api/web/extract",
        json={"url": "https://example.com/post", "save": True, "to_document": True},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["title"] == "识文台项目介绍"
    assert "OCR" in payload["content"]
    assert payload["author"] == "罗浩"
    assert payload["site"] == "示例站点"
    assert payload["word_count"] > 20
    assert payload["auto_opened"] is False
    assert payload["document_id"]
    assert any(url.endswith("cover.png") for url in payload["images"])
    assert any(url.endswith("screenshot-2.png") for url in payload["images"])

    document = client.get(f"/api/history/{payload['document_id']}")
    assert document.status_code == 200
    assert document.json()["source_type"] == "web"


def test_extract_record_history(client, monkeypatch):
    monkeypatch.setattr(
        web_extract_service.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(),
    )
    created = client.post(
        "/api/web/extract",
        json={"url": "https://example.com/history", "save": True},
    ).json()
    history = client.get("/api/web/history")
    assert history.status_code == 200
    assert any(item["id"] == created["id"] for item in history.json()["items"])

    detail = client.get(f"/api/web/records/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "识文台项目介绍"

    converted = client.post(f"/api/web/records/{created['id']}/to-document")
    assert converted.status_code == 200
    assert converted.json()["document"]["source_type"] == "web"


def test_extract_blocks_redirect_to_private(client, monkeypatch):
    redirect = FakeResponse(text="", status_code=302, headers={"Location": "http://10.0.0.5/secret"})
    monkeypatch.setattr(
        web_extract_service.requests,
        "get",
        lambda *args, **kwargs: redirect,
    )
    response = client.post("/api/web/extract", json={"url": "https://example.com/redirect"})
    assert response.status_code == 400


def test_extract_non_html_is_rejected(client, monkeypatch):
    monkeypatch.setattr(
        web_extract_service.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(text="{}", headers={"Content-Type": "application/json"}),
    )
    response = client.post("/api/web/extract", json={"url": "https://example.com/api"})
    assert response.status_code == 400
    assert "响应类型" in response.json()["detail"]
