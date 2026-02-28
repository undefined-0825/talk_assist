from __future__ import annotations

from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/version")
async def version():
    return {"app": settings.app_name, "version": settings.app_version, "commit": settings.commit_sha, "env": settings.app_env}
