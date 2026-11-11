"""FastAPI 应用入口。

职责：
* 初始化数据库、日志、目录与中断任务恢复；
* 注册中间件、异常处理与全部 REST 路由；
* 托管前端静态资源（单页应用）。

启动方式参见项目根目录 ``run.py``。
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import api_router
from .db import init_db
from .providers import ProviderError
from .services import cleanup, task_service
from .services.logging_config import setup_logging
from .services.web_extract_service import WebExtractError
from .utils.security import SecurityError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    config.ensure_dirs()
    init_db()
    interrupted = task_service.recover_interrupted()
    threading.Thread(target=cleanup.run_startup_maintenance, daemon=True, name="maintenance").start()

    logger.info(
        "%s v%s 已启动 | 数据目录：%s | 中断批次：%s",
        config.APP_NAME,
        config.VERSION,
        config.DATA_DIR,
        interrupted,
    )
    yield
    logger.info("服务已停止")


app = FastAPI(
    title=config.APP_NAME,
    description=config.APP_DESCRIPTION,
    version=config.VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Export-Count", "X-Response-Time"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """记录耗时并补充基础安全响应头。"""

    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers.setdefault("X-Response-Time", f"{elapsed_ms:.0f}ms")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if elapsed_ms > 2000 and request.url.path.startswith("/api"):
        logger.warning("慢请求 %s %s %.0fms", request.method, request.url.path, elapsed_ms)
    return response


@app.exception_handler(ProviderError)
async def handle_provider_error(_request: Request, exc: ProviderError):
    logger.warning("能力调用失败 [%s]：%s", exc.code, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc), "code": exc.code})


@app.exception_handler(SecurityError)
async def handle_security_error(_request: Request, exc: SecurityError):
    return JSONResponse(status_code=400, content={"detail": str(exc), "code": "security"})


@app.exception_handler(WebExtractError)
async def handle_web_error(_request: Request, exc: WebExtractError):
    return JSONResponse(status_code=400, content={"detail": str(exc), "code": "web_extract"})


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        errors.append(f"{location}: {error.get('msg')}")
    return JSONResponse(
        status_code=422,
        content={"detail": "请求参数有误", "code": "validation", "errors": errors[:8]},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, exc: Exception):  # pragma: no cover - 兜底
    logger.exception("未处理的异常：%s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请查看日志", "code": "internal"},
    )


app.include_router(api_router, prefix=config.API_PREFIX)


@app.get("/api", include_in_schema=False)
def api_index() -> dict:
    return {
        "app": config.APP_NAME,
        "version": config.VERSION,
        "docs": "/api/docs",
        "health": "/api/health",
    }


if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
else:  # pragma: no cover - 开发早期兜底
    @app.get("/", include_in_schema=False)
    def placeholder() -> dict:
        return {
            "message": "前端资源尚未构建，请访问 /api/docs 查看接口文档",
            "app": config.APP_NAME,
        }
