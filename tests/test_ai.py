"""AI 处理与问答接口测试。"""

from __future__ import annotations


def test_actions_catalog(client):
    response = client.get("/api/ai/actions")
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert {"translate", "summarize", "keywords", "qa", "polish", "outline"} <= actions


def test_providers_catalog(client):
    response = client.get("/api/ai/providers")
    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["items"]}
    assert {"mock", "deepseek", "kimi", "zhipu", "qwen", "custom"} <= names
    assert payload["default"] == "mock"


def test_summarize_text(client):
    text = (
        "识文台是一套 OCR 与 AI 结合的文字工作台。它支持批量识别、翻译、摘要、关键词与问答。"
        "所有数据保存在本机，密钥只存放在服务端。系统还提供网页提取与自动打开原文的能力。"
    )
    response = client.post(
        "/api/ai/process",
        json={"action": "summarize", "text": text, "options": {"length": "简短"}},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["output"]
    assert payload["provider"] == "mock"
    assert payload["demo"] is True
    assert payload["run_id"]


def test_translate_and_keywords(client):
    text = "Software engineering requires careful requirements analysis, design and testing."
    translation = client.post(
        "/api/ai/process",
        json={"action": "translate", "text": text, "options": {"target_language": "zh"}},
    )
    assert translation.status_code == 200
    assert "演示翻译" in translation.json()["output"]

    keywords = client.post(
        "/api/ai/process",
        json={"action": "keywords", "text": text * 3, "options": {"count": 5}},
    )
    assert keywords.status_code == 200
    assert "演示关键词" in keywords.json()["output"]


def test_process_with_document(client, document):
    response = client.post(
        "/api/ai/process",
        json={"action": "summarize", "document_id": document["document_id"]},
    )
    assert response.status_code == 200
    assert response.json()["document_id"] == document["document_id"]


def test_process_requires_text(client):
    response = client.post("/api/ai/process", json={"action": "summarize", "text": "   "})
    assert response.status_code == 400
    assert "没有可处理" in response.json()["detail"]


def test_process_unknown_action(client):
    response = client.post("/api/ai/process", json={"action": "unknown", "text": "hello"})
    assert response.status_code == 400


def test_process_missing_document(client):
    response = client.post(
        "/api/ai/process",
        json={"action": "summarize", "document_id": 999999, "text": "hello"},
    )
    assert response.status_code == 400
    assert "文档不存在" in response.json()["detail"]


def test_chat_conversation_flow(client, document):
    first = client.post(
        "/api/ai/chat",
        json={
            "message": "这段文本的主要内容是什么？",
            "document_id": document["document_id"],
        },
    )
    assert first.status_code == 200, first.text
    payload = first.json()
    conversation_id = payload["conversation"]["id"]
    assert payload["reply"]["content"]
    assert payload["reply"]["role"] == "assistant"
    assert len(payload["conversation"]["messages"]) == 2

    second = client.post(
        "/api/ai/chat",
        json={"message": "还有别的要点吗？", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    assert len(second.json()["conversation"]["messages"]) == 4

    listed = client.get("/api/ai/conversations")
    assert listed.status_code == 200
    assert any(item["id"] == conversation_id for item in listed.json()["items"])

    detail = client.get(f"/api/ai/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == conversation_id

    deleted = client.delete(f"/api/ai/conversations/{conversation_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/ai/conversations/{conversation_id}").status_code == 404


def test_chat_missing_conversation(client):
    response = client.post(
        "/api/ai/chat",
        json={"message": "你好", "conversation_id": 999999},
    )
    assert response.status_code == 400
