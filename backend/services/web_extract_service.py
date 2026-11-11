"""网页正文提取服务。

功能：
1. 安全抓取（SSRF 防护、超时、大小限制、逐跳校验重定向）；
2. 正文抽取（多候选容器打分，去除导航/广告/评论区）；
3. 元数据抽取（标题、作者、站点、发布时间、封面图）；
4. 与文字资产打通（可一键转为可编辑文档）；
5. 自动打开原始网页（桌面模式调用系统浏览器，Web 模式由前端新标签页打开）。

安全说明：服务器可能部署在云主机上，直接放开 URL 抓取会带来 SSRF 风险，
因此每一跳重定向都会重新校验目标地址。
"""

from __future__ import annotations

import re
import time
import webbrowser
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from .. import config
from ..models import Document, WebExtraction
from ..utils.security import SecurityError, validate_public_url
from ..utils.text import clean_text, count_chars, detect_language, truncate
from ..utils.time import now_iso

_MAX_REDIRECTS = 5
_MAX_CONTENT_CHARS = 80_000
_NOISE_TAGS = ("script", "style", "noscript", "svg", "iframe", "form", "button", "canvas")
_NOISE_HINTS = (
    "advert", "ads-", "banner", "comment", "share", "related", "sidebar", "footer",
    "header", "nav", "breadcrumb", "recommend", "cookie", "popup", "modal", "subscribe",
    "广告", "评论", "推荐", "相关阅读", "分享", "导航", "版权",
)
_CANDIDATE_SELECTORS = (
    "article",
    "main",
    "[role=main]",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".rich_media_content",
    ".markdown-body",
    "#content",
    "#article",
    ".content",
)


class WebExtractError(ValueError):
    """网页提取失败。"""


@dataclass(slots=True)
class FetchResult:
    final_url: str
    html: str
    content_type: str


def _fetch(url: str, timeout: int, max_bytes: int) -> FetchResult:
    """抓取网页，逐跳校验重定向，限制响应体大小。"""

    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        try:
            safe_url = validate_public_url(current)
        except SecurityError as exc:
            raise WebExtractError(str(exc)) from exc

        try:
            response = requests.get(
                safe_url,
                headers=headers,
                timeout=(5, timeout),
                stream=True,
                allow_redirects=False,
            )
        except requests.Timeout as exc:
            raise WebExtractError("抓取超时，请检查网络或稍后重试") from exc
        except requests.RequestException as exc:
            raise WebExtractError(f"网络请求失败：{exc}") from exc

        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise WebExtractError("网页返回了无目标的重定向")
            current = urljoin(safe_url, location)
            continue

        if response.status_code >= 400:
            response.close()
            raise WebExtractError(f"网页返回 HTTP {response.status_code}")

        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            response.close()
            raise WebExtractError(f"不支持的响应类型：{content_type or '未知'}")

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                response.close()
                raise WebExtractError(f"网页内容超过 {max_bytes // 1000}KB 限制")
            chunks.append(chunk)
        response.close()

        raw = b"".join(chunks)
        encoding = response.encoding
        if not encoding or encoding.lower() in {"iso-8859-1", "ascii"}:
            encoding = response.apparent_encoding or "utf-8"
        html = raw.decode(encoding, errors="replace")
        return FetchResult(final_url=safe_url, html=html, content_type=content_type)

    raise WebExtractError("重定向次数过多")


def _json_ld(soup: BeautifulSoup) -> dict:
    """解析 JSON-LD，提取作者、发布时间等信息。"""

    import json

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            if "@graph" in item and isinstance(item["@graph"], list):
                candidates.extend(item["@graph"])
            author = item.get("author")
            if isinstance(author, list):
                author = author[0] if author else None
            if isinstance(author, dict):
                author = author.get("name")
            return {
                "title": item.get("headline") or item.get("name"),
                "author": author,
                "published_at": item.get("datePublished"),
                "site": item.get("publisher", {}).get("name") if isinstance(item.get("publisher"), dict) else None,
                "image": item.get("image") if isinstance(item.get("image"), str) else None,
            }
    return {}


def _meta(soup: BeautifulSoup) -> dict:
    def content(*selectors: str) -> str | None:
        for selector in selectors:
            node = soup.select_one(selector)
            if node and node.get("content"):
                return str(node["content"]).strip()
        return None

    return {
        "title": content('meta[property="og:title"]', 'meta[name="twitter:title"]'),
        "site": content('meta[property="og:site_name"]', 'meta[name="application-name"]'),
        "author": content('meta[name="author"]', 'meta[property="article:author"]'),
        "published_at": content(
            'meta[property="article:published_time"]',
            'meta[name="publishdate"]',
            'meta[name="date"]',
        ),
        "image": content('meta[property="og:image"]', 'meta[name="twitter:image"]'),
        "description": content('meta[property="og:description"]', 'meta[name="description"]'),
    }


def _strip_noise(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
    for element in soup.find_all(True):
        identifier = " ".join(
            filter(None, [element.get("id") or "", " ".join(element.get("class") or [])])
        ).lower()
        if identifier and any(hint in identifier for hint in _NOISE_HINTS):
            # 避免误删正文容器：仅删除明显是噪音且文本量较小的节点
            if len(element.get_text(strip=True)) < 2000:
                element.decompose()


def _score(node) -> float:
    text = node.get_text(" ", strip=True)
    if len(text) < 80:
        return -1.0
    link_text = sum(len(link.get_text(strip=True)) for link in node.find_all("a"))
    link_density = min(0.9, link_text / max(1, len(text)))
    paragraphs = len(node.find_all("p"))
    return len(text) * (1 - link_density) + paragraphs * 80


def _pick_container(soup: BeautifulSoup):
    best = None
    best_score = -1.0
    for selector in _CANDIDATE_SELECTORS:
        for node in soup.select(selector):
            score = _score(node)
            if score > best_score:
                best, best_score = node, score
    body = soup.body or soup
    body_score = _score(body)
    if body_score > best_score:
        best, best_score = body, body_score
    return best or body


def _extract_body(container) -> str:
    blocks: list[str] = []
    seen: set[str] = set()
    for node in container.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "pre", "td"]):
        text = node.get_text(" ", strip=True)
        text = re.sub(r"[ \t\u3000]+", " ", text).strip()
        if not text or len(text) < 2:
            continue
        if text in seen:
            continue
        if len(text) < 8 and node.name not in {"h1", "h2", "h3", "h4"}:
            continue
        seen.add(text)
        if node.name in {"h1", "h2", "h3", "h4"}:
            blocks.append(f"\n## {text}\n")
        else:
            blocks.append(text)
    content = "\n\n".join(blocks)
    if count_chars(content) < 60:
        content = container.get_text("\n", strip=True)
    return truncate(clean_text(content), _MAX_CONTENT_CHARS, suffix="")


def _extract_images(soup: BeautifulSoup, container, base_url: str, cover: str | None) -> list[str]:
    urls: list[str] = []
    if cover:
        urls.append(urljoin(base_url, cover))
    for image in list(container.find_all("img")) + list(soup.find_all("img"))[:30]:
        source = (
            image.get("src")
            or image.get("data-src")
            or image.get("data-original")
            or image.get("data-lazy-src")
        )
        if not source:
            continue
        absolute = urljoin(base_url, str(source).strip())
        if absolute.startswith(("data:", "javascript:")):
            continue
        if absolute not in urls:
            urls.append(absolute)
    return urls[:30]


def _save_document(
    db: Session,
    *,
    title: str,
    content: str,
    final_url: str,
    site: str | None,
    author: str | None,
    images: list[str],
    extraction_id: int | None,
) -> Document:
    document = Document(
        title=(title or "网页提取")[:255],
        filename=None,
        source_type="web",
        source_url=final_url,
        content=content,
        original_content=content,
        engine="web",
        language=detect_language(content),
        confidence=1.0,
        char_count=count_chars(content),
        status="ok",
        tags="[]",
    )
    document.meta_dict = {
        "site": site,
        "author": author,
        "images": images[:12],
        "extraction_id": extraction_id,
    }
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def extract(
    db: Session,
    settings: dict,
    url: str,
    *,
    save: bool = True,
    to_document: bool = False,
    auto_open: bool | None = None,
) -> dict:
    """提取网页正文。"""

    started = time.perf_counter()
    timeout = int(settings.get("web_timeout", 20))
    max_bytes = int(settings.get("web_max_bytes", 3_000_000))

    fetched = _fetch(url, timeout, max_bytes)
    soup = BeautifulSoup(fetched.html, "html.parser")
    json_ld = _json_ld(soup)
    meta = _meta(soup)

    title = (
        json_ld.get("title")
        or meta.get("title")
        or (soup.h1.get_text(" ", strip=True) if soup.h1 else None)
        or (soup.title.get_text(strip=True) if soup.title else None)
        or urlsplit(fetched.final_url).netloc
    )
    title = re.sub(r"\s+", " ", str(title)).strip()[:500]
    title = re.sub(r"\s*[-_|｜]\s*[^-_|｜]{1,30}$", "", title) or title

    _strip_noise(soup)
    container = _pick_container(soup)
    content = _extract_body(container)
    if count_chars(content) < 30:
        raise WebExtractError("未能从该网页提取到有效正文，可能是动态渲染页面或需要登录")

    site = meta.get("site") or json_ld.get("site") or urlsplit(fetched.final_url).netloc
    author = meta.get("author") or json_ld.get("author")
    published_at = meta.get("published_at") or json_ld.get("published_at")
    images = _extract_images(soup, container, fetched.final_url, meta.get("image") or json_ld.get("image"))
    summary = truncate(content, 180)
    word_count = count_chars(content)
    elapsed = (time.perf_counter() - started) * 1000

    record_id = None
    if save:
        record = WebExtraction(
            url=url,
            final_url=fetched.final_url,
            title=title,
            author=str(author)[:255] if author else None,
            site=str(site)[:255] if site else None,
            published_at=str(published_at)[:64] if published_at else None,
            content=content,
            summary=summary,
            word_count=word_count,
            status="ok",
        )
        record.images_list = images
        db.add(record)
        db.commit()
        db.refresh(record)
        record_id = record.id

    document_id = None
    if to_document:
        document = _save_document(
            db,
            title=title,
            content=content,
            final_url=fetched.final_url,
            site=str(site) if site else None,
            author=str(author) if author else None,
            images=images,
            extraction_id=record_id,
        )
        document_id = document.id

    should_open = settings.get("auto_open_web", True) if auto_open is None else bool(auto_open)
    opened = False
    if should_open and config.is_desktop_mode():
        opened = open_in_system_browser(fetched.final_url)

    return {
        "id": record_id,
        "url": url,
        "final_url": fetched.final_url,
        "title": title,
        "author": str(author) if author else None,
        "site": str(site) if site else None,
        "published_at": str(published_at) if published_at else None,
        "content": content,
        "summary": summary,
        "images": images,
        "word_count": word_count,
        "elapsed_ms": round(elapsed, 1),
        "auto_opened": opened,
        "document_id": document_id,
        "notice": "已在系统浏览器中打开原文" if opened else None,
    }


def open_in_system_browser(url: str) -> bool:
    """调用操作系统默认浏览器打开指定 URL。"""

    try:
        safe_url = validate_public_url(url)
    except SecurityError:
        return False
    try:
        return webbrowser.open(safe_url, new=2, autoraise=True)
    except Exception:  # pragma: no cover - 依赖桌面环境
        return False


def open_url(url: str) -> dict:
    """显式打开网页。桌面模式使用系统浏览器，服务器模式提示由前端打开。"""

    try:
        safe_url = validate_public_url(url)
    except SecurityError as exc:
        raise WebExtractError(str(exc)) from exc

    if config.is_desktop_mode():
        opened = open_in_system_browser(safe_url)
        return {
            "ok": True,
            "opened": opened,
            "mode": "system",
            "message": "已调用系统默认浏览器" if opened else "系统浏览器调用失败，请在浏览器中手动打开",
        }
    return {
        "ok": True,
        "opened": False,
        "mode": "browser",
        "message": "当前为服务器模式，请在浏览器新标签页中打开",
    }


def recent(db: Session, limit: int = 20) -> list[WebExtraction]:
    from sqlalchemy import select

    return list(
        db.scalars(select(WebExtraction).order_by(WebExtraction.created_at.desc()).limit(limit)).all()
    )


def record_to_document(db: Session, record_id: int) -> Document:
    """把已保存的网页提取记录转换为可编辑的文字资产。"""

    record = db.get(WebExtraction, record_id)
    if record is None:
        raise WebExtractError("网页提取记录不存在")

    if record.document_id:
        existing = db.get(Document, record.document_id)
        if existing is not None:
            return existing

    document = _save_document(
        db,
        title=record.title,
        content=record.content,
        final_url=record.final_url or record.url,
        site=record.site,
        author=record.author,
        images=record.images_list,
        extraction_id=record.id,
    )
    record.document_id = document.id
    db.commit()
    return document


def record_out(record: WebExtraction) -> dict:
    return {
        "id": record.id,
        "url": record.url,
        "final_url": record.final_url,
        "title": record.title,
        "author": record.author,
        "site": record.site,
        "published_at": record.published_at,
        "content": record.content,
        "summary": record.summary,
        "images": record.images_list,
        "word_count": record.word_count,
        "status": record.status,
        "document_id": record.document_id,
        "created_at": record.created_at,
        "extracted_at": now_iso(),
    }
