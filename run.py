"""识文台 InsightDesk 启动脚本。

用法::

    python run.py                  # 默认 127.0.0.1:8770，并自动打开浏览器
    python run.py --port 9000      # 指定端口
    python run.py --no-browser     # 不自动打开浏览器
    python run.py --reload         # 开发模式热重载

浏览器自动打开是需求 FR-09 的一部分：启动后无需手动复制地址。
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# 确保以脚本方式运行时能导入 backend 包
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def find_free_port(preferred: int = 8770, attempts: int = 40) -> int:
    """从首选端口开始寻找可用端口。"""

    for offset in range(attempts):
        candidate = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_and_open(url: str, host: str, port: int, timeout: float = 30.0) -> None:
    """等待服务端口可连接后打开默认浏览器。"""

    deadline = time.time() + timeout
    target_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.6)
            if sock.connect_ex((target_host, port)) == 0:
                try:
                    webbrowser.open(url, new=2, autoraise=True)
                except Exception:
                    pass
                return
        time.sleep(0.35)


def main() -> None:
    parser = argparse.ArgumentParser(description="识文台 InsightDesk 本地启动器")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=0, help="监听端口（默认自动选择 8770 起）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--reload", action="store_true", help="开发模式：代码变更自动重载")
    args = parser.parse_args()

    port = args.port or find_free_port()
    url = f"http://{'127.0.0.1' if args.host in {'0.0.0.0', '::'} else args.host}:{port}"

    banner = f"""
╭──────────────────────────────────────────────╮
│  识文台 InsightDesk · OCR + AI 智能文字工作台  │
│  地址：{url:<36}│
│  文档：{url + '/api/docs':<36}│
│  退出：按 Ctrl + C                             │
╰──────────────────────────────────────────────╯
"""
    print(banner, flush=True)

    if not args.no_browser:
        threading.Thread(
            target=wait_and_open,
            args=(url, args.host, port),
            daemon=True,
            name="open-browser",
        ).start()

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=port,
        reload=args.reload,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
