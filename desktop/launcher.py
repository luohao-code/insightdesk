"""桌面版启动器。

被 PyInstaller 打包后，双击 exe 即：
1. 在用户 AppData 目录准备数据目录；
2. 启动本地 Web 服务（仅监听 127.0.0.1）；
3. 自动打开系统默认浏览器访问应用首页（需求 FR-09）。

与 ``run.py`` 的区别：本文件面向打包后的可执行环境，处理资源路径、
日志落盘与异常弹窗，不依赖控制台。
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path


def _base_dir() -> Path:
    """PyInstaller 解包目录（只读资源）或源码目录。"""

    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def _prepare_environment() -> Path:
    """设置环境变量并返回用户数据目录。"""

    base = _base_dir()
    data_dir = Path(os.environ.get("APPDATA") or Path.home()) / "InsightDesk" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("INSIGHTDESK_DATA_DIR", str(data_dir))
    os.environ.setdefault("INSIGHTDESK_DESKTOP", "1")
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    return data_dir


def _find_port(preferred: int = 8770) -> int:
    for candidate in range(preferred, preferred + 40):
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


def _open_browser(url: str, port: int, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.8)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                try:
                    webbrowser.open(url, new=2, autoraise=True)
                except Exception:
                    pass
                return
        time.sleep(0.4)


def _show_error(message: str) -> None:
    """打包为无控制台程序时，用系统弹窗提示致命错误。"""

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "识文台 InsightDesk 启动失败", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def main() -> int:
    data_dir = _prepare_environment()
    port = _find_port()
    url = f"http://127.0.0.1:{port}"

    try:
        from backend.main import app
        import uvicorn

        # 日志同时写入数据目录，便于用户反馈问题
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        threading.Thread(target=_open_browser, args=(url, port), daemon=True).start()

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False,
            log_config=None,
        )
    except Exception as exc:  # pragma: no cover - 桌面异常路径
        detail = f"{exc}\n\n{traceback.format_exc()}"
        (data_dir / "logs").mkdir(parents=True, exist_ok=True)
        (data_dir / "logs" / "launcher_error.log").write_text(detail, encoding="utf-8")
        _show_error(f"程序启动失败：{exc}\n\n详细信息已写入：{data_dir / 'logs'}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
