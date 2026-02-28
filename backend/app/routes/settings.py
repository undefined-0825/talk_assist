from __future__ import annotations

import datetime as dt
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models import UserSettings
from app.schemas import SettingsResponse, SettingsUpdateRequest
from app.security import get_auth_context, AuthContext
from app.utils import etag_for_json
from app.errors import err

router = APIRouter()


@router.get("/me/settings", response_model=SettingsResponse)
async def get_settings(
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    row = await db.execute(select(UserSettings).where(UserSettings.user_id == auth.user_id))
    st = row.scalar_one_or_none()
    if not st:
        # 自動復旧（本文保存なし・設定メタのみ）
        settings_json = {"settings_schema_version": 1, "persona_version": 2}
        etag = etag_for_json(settings_json)
        st = UserSettings(
            user_id=auth.user_id,
            settings_json=settings_json,
            settings_schema_version=1,
            etag=etag,
            updated_at=dt.datetime.now(dt.timezone.utc),
        )
        db.add(st)
        await db.commit()

    response.headers["ETag"] = st.etag
    return SettingsResponse(settings=st.settings_json)


@router.put("/me/settings", response_model=SettingsResponse)
async def put_settings(
    req: SettingsUpdateRequest,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if not if_match:
        raise err("VALIDATION_FAILED", "If-Matchが必要です", status_code=422)

    row = await db.execute(select(UserSettings).where(UserSettings.user_id == auth.user_id))
    st = row.scalar_one_or_none()
    if not st:
        raise err("SETTINGS_VERSION_CONFLICT", "設定が競合しました", status_code=409)

    if st.etag != if_match:
        raise err("SETTINGS_VERSION_CONFLICT", "設定が競合しました", status_code=409)

    # settings_schema_version必須（未知フィールド許容）
    s = dict(req.settings or {})
    if "settings_schema_version" not in s:
        # サーバがSSOTなので補完（ただしクライアントのバージョン管理を壊さない最小）
        s["settings_schema_version"] = st.settings_schema_version or 1

    new_etag = etag_for_json(s)
    st.settings_json = s
    st.settings_schema_version = int(s.get("settings_schema_version") or 1)
    st.etag = new_etag
    st.updated_at = dt.datetime.now(dt.timezone.utc)

    await db.commit()

    response.headers["ETag"] = new_etag
    return SettingsResponse(settings=st.settings_json)
