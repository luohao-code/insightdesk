"""健康检查与系统信息测试。"""

from __future__ import annotations

from backend import config


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["app"] == config.APP_NAME
    assert payload["database"]["status"] == "ok"
    assert "mock" in payload["engines"]["available"]
    assert payload["desktop_mode"] is False


def test_system_info(client):
    response = client.get("/api/system/info")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == config.VERSION
    assert payload["python"]
    assert "storage" in payload
    assert payload["engines"]["ocr_default"]


def test_api_index(client):
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json()["health"] == "/api/health"


def test_logs_endpoint(client):
    response = client.get("/api/system/logs?lines=10")
    assert response.status_code == 200
    assert isinstance(response.json()["lines"], list)


def test_cleanup_endpoint_dry_run(client):
    response = client.post("/api/system/cleanup?days=30&dry_run=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["dry_run"] is True
