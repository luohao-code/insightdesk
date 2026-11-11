# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

构建：
    python scripts/make_icon.py
    pyinstaller desktop/insightdesk.spec --noconfirm
"""

import os

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC)) if "SPEC" in globals() else os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(SPEC_DIR, ".."))

hiddenimports = collect_submodules("uvicorn") + [
    "anyio._backends._asyncio",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.sql.default_comparator",
    "email.mime.multipart",
    "email.mime.text",
]

datas = [
    (os.path.join(ROOT, "frontend"), "frontend"),
]

a = Analysis(
    [os.path.join(ROOT, "desktop", "launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除体积大且非必需的依赖；RapidOCR 通过可选安装动态加载
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy", "onnxruntime"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="InsightDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "desktop", "icon.ico") if os.path.exists(os.path.join(ROOT, "desktop", "icon.ico")) else None,
)
