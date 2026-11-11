"""工具函数与提示词测试。"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from backend.prompts import build_prompt, get_spec, list_actions
from backend.utils import images, security, text
from backend.utils.files import human_size, safe_filename, sha1_bytes
from backend.utils.time import human_duration


def test_clean_text_and_merge_lines():
    raw = "识文台是一套工作台，\n支持 OCR 与 AI。\n\n第二段内容\n继续同一段。"
    merged = text.merge_soft_wraps(raw)
    assert "工作台，支持 OCR" in merged
    assert "\n\n" in merged


def test_count_and_language():
    assert text.count_chars("你好 world") == 7
    assert text.detect_language("这是中文文本") == "zh"
    assert text.detect_language("This is English text") == "en"
    assert text.detect_language("中文 and English mixed") == "mixed"
    assert text.detect_language("") == "unknown"


def test_keywords_and_summary():
    content = (
        "软件工程强调需求分析。需求分析是软件工程的重要阶段。"
        "设计阶段需要关注架构。测试阶段需要覆盖需求。软件工程需要文档。"
    )
    keywords = text.word_frequency(content, limit=8)
    assert keywords
    summary = text.extractive_summary(content, max_sentences=2)
    assert summary
    assert len(summary) < len(content)


def test_demo_translate_and_answer():
    translated = text.demo_translate("software engineering requirements", "zh")
    assert "软件" in translated
    answer = text.demo_answer("需求分析重要吗", "软件工程强调需求分析，需求分析非常重要。")
    assert "需求分析" in answer


def test_csv_safe():
    assert text.csv_safe("=1+1").startswith("'")
    assert text.csv_safe("正常内容") == "正常内容"
    assert text.csv_safe("") == ""


def test_truncate_and_slugify():
    assert text.truncate("abcdef", 3) == "abc…"
    assert text.slugify("识文台 OCR 工作台") == "识文台-OCR-工作台"


def test_secret_masking():
    assert security.mask_secret("") == ""
    assert security.mask_secret("abc") == "••••••••"
    assert security.is_masked("••••••••")
    assert security.mask_secret("sk-1234567890abcdef").startswith("sk-")
    assert "*" in security.mask_secret("sk-1234567890abcdef")


def test_safe_join(tmp_path):
    inside = security.safe_join(tmp_path, "a", "b.txt")
    assert str(inside).startswith(str(tmp_path))
    with pytest.raises(security.SecurityError):
        security.safe_join(tmp_path, "..", "outside.txt")


def test_validate_url_rejects_private(monkeypatch):
    with pytest.raises(security.SecurityError):
        security.validate_public_url("http://127.0.0.1/")
    with pytest.raises(security.SecurityError):
        security.validate_public_url("ftp://example.com/file")
    with pytest.raises(security.SecurityError):
        security.validate_public_url("http://user:pass@example.com/")

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    normalized = security.validate_public_url("https://example.com/path#fragment")
    assert normalized == "https://example.com/path"


def test_validate_url_rejects_private_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))],
    )
    with pytest.raises(security.SecurityError):
        security.validate_public_url("https://internal.example.com/")


def test_files_helpers(tmp_path):
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("") == "image"
    assert human_size(2048) == "2.0 KB"
    assert sha1_bytes(b"abc") == "a9993e364706816aba3e25717850c26c9cd0d89d"

    target = tmp_path / "x.txt"
    target.write_text("hello", encoding="utf-8")
    assert target.exists()


def test_time_helpers():
    assert human_duration(None) == "-"
    assert human_duration(500).endswith("ms")
    assert "秒" in human_duration(1500)
    assert "分" in human_duration(65_000)


def test_image_probe_and_thumbnail(tmp_path):
    from PIL import Image, ImageDraw

    source = tmp_path / "sample.png"
    image = Image.new("RGB", (640, 360), "white")
    ImageDraw.Draw(image).text((20, 40), "InsightDesk", fill="black")
    image.save(source)

    info = images.probe_image(source)
    assert info.width == 640
    assert info.height == 360
    assert info.format == "PNG"

    thumb = tmp_path / "thumb.png"
    images.make_thumbnail(source, thumb, (120, 120))
    assert thumb.exists()
    with Image.open(thumb) as rendered:
        assert max(rendered.size) <= 120


def test_image_rejects_invalid(tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    with pytest.raises(images.ImageError):
        images.probe_image(broken)


def test_prompt_library():
    actions = {item["action"] for item in list_actions()}
    assert {"translate", "summarize", "keywords", "qa"} <= actions

    bundle = build_prompt("translate", "hello world", {"target_language": "zh"})
    assert "简体中文" in bundle.user
    assert "hello world" in bundle.user
    assert bundle.system

    with pytest.raises(KeyError):
        get_spec("unknown")

    long_text = "字" * 20_000
    truncated = build_prompt("summarize", long_text)
    assert truncated.truncated is True
    assert "已截断" in truncated.user
