from __future__ import annotations

from fastapi import APIRouter, Request, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import User, UserSettings, PlanStatus
from app.schemas import AuthAnonymousResponse
from app.security import create_session
from app.ratelimit import fixed_window_limit
from app.utils import etag_for_json

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/anonymous", response_model=AuthAnonymousResponse)
async def auth_anonymous(
    request: Request,
    db: AsyncSession = Depends(get_db),
    device_fingerprint: str | None = Header(default=None, alias="X-Device-Fingerprint"),
):
    ip = _client_ip(request)
    await fixed_window_limit(f"rl:auth:ip:{ip}:10m", settings.rl_auth_ip_limit, settings.rl_auth_ip_window_seconds)
    if device_fingerprint:
        await fixed_window_limit(f"rl:auth:df:{device_fingerprint}:10m", settings.rl_auth_df_limit, settings.rl_auth_df_window_seconds)

    user = User()
    db.add(user)
    await db.flush()

    # plan_status SSOT
    db.add(PlanStatus(user_id=user.user_id, plan="free"))

    # 初期settings（未知フィールド許容のため JSONそのまま）
    initial = {"settings_schema_version": 1, "persona_version": 2}
    etag = etag_for_json(initial)
    db.add(UserSettings(user_id=user.user_id, settings_json=initial, settings_schema_version=1, etag=etag))

    await db.commit()

    token = await create_session(user.user_id)
    return AuthAnonymousResponse(user_id=user.user_id, access_token=token)
