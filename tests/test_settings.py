"""设置接口测试。"""

from __future__ import annotations


def test_get_settings_masks_secrets(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    payload = response.json()
    assert "values" in payload
    assert "engines" in payload
    assert payload["values"]["ai_api_key"] in {"", "••••••••"}


def test_update_concurrency(client):
    response = client.put("/api/settings", json={"values": {"concurrency": 4}})
    assert response.status_code == 200
    assert response.json()["values"]["concurrency"] == 4

    restored = client.put("/api/settings", json={"values": {"concurrency": 3}})
    assert restored.status_code == 200


def test_update_out_of_range(client):
    response = client.put("/api/settings", json={"values": {"concurrency": 99}})
    assert response.status_code == 400
    assert "1" in response.json()["detail"]


def test_update_unknown_engine(client):
    response = client.put("/api/settings", json={"values": {"ocr_engine": "not-exist"}})
    assert response.status_code == 400
    assert "未知" in response.json()["detail"]


def test_update_secret_and_masking(client):
    response = client.put("/api/settings", json={"values": {"ai_api_key": "sk-test-secret-123456"}})
    assert response.status_code == 200
    assert response.json()["values"]["ai_api_key"] == "••••••••"

    # 提交掩码表示保持原值
    keep = client.put("/api/settings", json={"values": {"ai_api_key": "••••••••"}})
    assert keep.status_code == 200

    from backend.db import SessionLocal
    from backend.services import settings_service

    with SessionLocal() as db:
        assert settings_service.get_all(db)["ai_api_key"] == "sk-test-secret-123456"
        settings_service.update(db, {"ai_api_key": ""})


def test_theme_validation(client):
    response = client.put("/api/settings", json={"values": {"theme": "rainbow"}})
    assert response.status_code == 400


def test_empty_update(client):
    response = client.put("/api/settings", json={"values": {}})
    assert response.status_code == 400


def test_test_provider_mock_ocr(client):
    response = client.post("/api/settings/test", json={"kind": "ocr", "name": "mock"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["latency_ms"] >= 0


def test_test_provider_mock_ai(client):
    response = client.post("/api/settings/test", json={"kind": "ai", "name": "mock"})
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_test_provider_unknown(client):
    response = client.post("/api/settings/test", json={"kind": "ocr", "name": "unknown"})
    assert response.status_code == 404


def test_test_provider_without_credentials(client):
    response = client.post("/api/settings/test", json={"kind": "ocr", "name": "baidu"})
    assert response.status_code == 200
    assert response.json()["ok"] is False
