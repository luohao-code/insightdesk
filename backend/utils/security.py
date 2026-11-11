"""通用工具：安全相关。

重点解决三类风险：

1. **SSRF**：网页提取功能允许用户输入任意 URL，必须阻止访问内网、环回、
   链路本地与保留地址，防止攻击者借此探测内网服务；
2. **密钥泄漏**：设置接口返回时必须脱敏；
3. **路径穿越**：所有落盘路径必须位于数据目录之内。
"""

from __future__ import annotations

import hmac
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .. import config

#: 常见内网主机名
_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}

#: 允许的端口（留空表示不限制；Web 抓取通常为 80/443/8080/8443）
_ALLOWED_PORTS = {None, 80, 443, 8080, 8443, 8000, 3000}


class SecurityError(ValueError):
    """安全校验失败。"""


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """校验并规范化外部 URL，阻止 SSRF。

    :raises SecurityError: URL 非法、含认证信息、端口不允许或解析到非公网地址
    """

    value = (url or "").strip()
    if not value:
        raise SecurityError("URL 不能为空")
    if len(value) > 2048:
        raise SecurityError("URL 过长")
    if not value.startswith(("http://", "https://")):
        raise SecurityError("仅支持 http/https 协议")

    parts = urlsplit(value)
    if not parts.netloc:
        raise SecurityError("URL 缺少主机名")
    if parts.username or parts.password:
        raise SecurityError("URL 不允许包含认证信息")
    if parts.port is not None and parts.port not in _ALLOWED_PORTS:
        raise SecurityError(f"不允许访问端口 {parts.port}")

    hostname = (parts.hostname or "").strip().lower()
    if not hostname:
        raise SecurityError("URL 缺少主机名")
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".local"):
        raise SecurityError("不允许访问本机或本地网络地址")

    # 直接使用 IP 的情况
    try:
        if not _is_public_ip(hostname):
            raise SecurityError("不允许访问内网地址")
    except ValueError:
        # 域名：解析全部 A/AAAA 记录，任意一个为内网地址即拒绝
        try:
            infos = socket.getaddrinfo(hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise SecurityError(f"域名解析失败：{hostname}") from exc
        addresses = {info[4][0] for info in infos}
        if not addresses:
            raise SecurityError("域名未解析到有效地址")
        for address in addresses:
            if not _is_public_ip(address):
                raise SecurityError("域名解析到内网地址，已阻止访问")

    # 规范化：去除片段（对抓取无意义）
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def redact_url(url: str) -> str:
    """去除 URL 中的认证信息与敏感查询参数，用于日志与错误提示。"""

    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    netloc = parts.netloc
    if parts.username or parts.password:
        netloc = parts.hostname or ""
        if parts.port:
            netloc += f":{parts.port}"
    pairs = []
    for pair in parts.query.split("&"):
        if not pair:
            continue
        key = pair.split("=", 1)[0].lower()
        if key in {"token", "key", "secret", "password", "access_token", "api_key"}:
            pairs.append(f"{key}=***")
        else:
            pairs.append(pair)
    query = "&".join(pairs)
    return urlunsplit((parts.scheme, netloc, parts.path, query, ""))


def mask_secret(value: str | None) -> str:
    """脱敏显示密钥：保留首尾少量字符。"""

    if not value:
        return ""
    text = str(value)
    if len(text) <= 4:
        return config.SECRET_MASK
    if len(text) <= 10:
        return text[:1] + "*" * (len(text) - 2) + text[-1:]
    return f"{text[:3]}{'*' * 8}{text[-3:]}"


def is_masked(value: str | None) -> bool:
    return value == config.SECRET_MASK or (bool(value) and set(str(value)) <= {"*", "•"})


def constant_time_compare(left: str, right: str) -> bool:
    """常量时间字符串比较，避免时序侧信道。"""

    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def safe_join(base: Path, *parts: str) -> Path:
    """安全拼接路径，阻止 ``..`` 穿越。"""

    candidate = base.joinpath(*parts).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise SecurityError("非法路径") from exc
    return candidate
