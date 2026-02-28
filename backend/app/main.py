from __future__ import annotations

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_conf import configure_logging
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.no_cache import NoCacheMiddleware

from app.routes.health import router as health_router
from app.routes.version import router as version_router
from app.routes.auth import router as auth_router
from app.routes.settings import router as settings_router
from app.routes.generate import router as generate_router
from app.routes.migration import router as migration_router


configure_logging()
log = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(NoCacheMiddleware)

app.include_router(health_router)
app.include_router(version_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(generate_router)
app.include_router(migration_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", "") or ""
    log.exception("unhandled_error", extra={"request_id": rid, "path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "内部エラーです", "detail": {}}},
        headers={"X-Request-Id": rid},
    )
